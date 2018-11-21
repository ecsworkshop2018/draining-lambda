import json
import boto3
import logging

LIST_LAST_ELEMENT = -1

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    The entry function of the lambda
    :param event: Message from ASG Termination hook delivers to SQS which triggers this lambda.
    :param context: Information about runtime context
    :return: None
    """
    logger.info("Received event: %s", event)
    drain_ecs_cluster_instances(event)
    return


def drain_ecs_cluster_instances(event):
    event_body = parse_event(event)
    container_instances = get_all_container_instances(_cluster_name(event_body))
    (container_instance_arn, ci_status, ci_running_tasks) = \
        get_container_instance_information(event_body["EC2InstanceId"], container_instances)

    operations = get_draining_operations(event, _cluster_name(event_body), container_instance_arn, ci_status,
                                         ci_running_tasks)

    for operation in operations:
        operation.perform()

    return


def parse_event(event):
    event_body = json.loads(event["Records"][0]["body"])
    event_body["NotificationMetadata"] = json.loads(event_body["NotificationMetadata"])
    return event_body


def _cluster_name(event_body):
    return event_body["NotificationMetadata"]["cluster-name"]


def get_all_container_instances(cluster_name):
    ecs_client = boto3.client('ecs')
    cluster_instances = ecs_client.list_container_instances(cluster=cluster_name)
    return ecs_client.describe_container_instances(cluster=cluster_name,
                                                   containerInstances=cluster_instances['containerInstanceArns'])


def get_container_instance_information(ec2_instance_id, container_instances):
    for ci in container_instances['containerInstances']:
        if ci['ec2InstanceId'] == ec2_instance_id:
            return ci['containerInstanceArn'], ci['status'], ci['runningTasksCount']

    return None, None, 0


def get_draining_operations(event, cluster_name, container_arn, status, running_tasks):
    if not container_arn:
        logging.warn("Instance not found with id %s. Possibly the hook timeout has exceeded.",
                     parse_event(event)["EC2InstanceId"])
        return []
    elif status != "DRAINING":
        logging.debug("Found instance status %s not DRAINING.", status)
        return [InstanceDrainingOperation(cluster_name, _extract_container_instance_id(container_arn)),
                RetriggerLambdaOperation(_queue_name(event), _event_body_str(event))]
    elif running_tasks > 0:
        logging.debug("Found %d running tasks", running_tasks)
        return [RetriggerLambdaOperation(_queue_name(event), _event_body_str(event))]
    else:
        return [TerminateInstanceOperation(prepare_complete_lifecycle_request(_event_body_str(event)))]


def _extract_container_instance_id(container_instance_arn):
    return container_instance_arn.split('/')[1]


def _event_body_str(event):
    return event["Records"][0]["body"]


def _queue_name(event):
    return event["Records"][0]["eventSourceARN"].split(":")[LIST_LAST_ELEMENT]


def prepare_complete_lifecycle_request(event_body_str):
    event_body = json.loads(event_body_str)
    return {
        "AutoScalingGroupName": event_body["AutoScalingGroupName"],
        "LifecycleActionResult": "CONTINUE",
        "LifecycleActionToken": event_body["LifecycleActionToken"],
        "LifecycleHookName": event_body["LifecycleHookName"],
        "InstanceId": event_body["EC2InstanceId"]
    }


class InstanceDrainingOperation:
    def __init__(self, cluster_name, container_instance_id):
        self.cluster_name = cluster_name
        self.container_instance_id = container_instance_id

    def perform(self):
        logging.info("Starting draining on container instance: %s, on %s cluster", self.container_instance_id,
                     self.cluster_name)
        ecs_client = boto3.client('ecs')
        ecs_client.update_container_instances_state(cluster=self.cluster_name,
                                                    containerInstances=[self.container_instance_id], status='DRAINING')


class RetriggerLambdaOperation:

    def __init__(self, queue_name, lambda_event):
        self.queue_name = queue_name
        self.lambda_event = lambda_event

    def sqs_client(self):
        return boto3.client('sqs')

    def perform(self):
        queue_url = self._queue_url()
        logging.info("Retriggering lambda with queue url: %s, and message: %s", queue_url, self.lambda_event)
        self.sqs_client().send_message(QueueUrl=queue_url, MessageBody=self.lambda_event)

    def _queue_url(self):
        logging.info("fetching queue url from queue %s", self.queue_name)
        return self.sqs_client().get_queue_url(QueueName=self.queue_name)["QueueUrl"]


class TerminateInstanceOperation:
    def __init__(self, complete_lifecyle_request):
        self.complete_lifecyle_request = complete_lifecyle_request

    def perform(self):
        logging.info("Completing the instance lifecycle with details: %s", self.complete_lifecyle_request)
        asg_client = boto3.client('autoscaling')
        asg_client.complete_lifecycle_action(**self.complete_lifecyle_request)
        return
