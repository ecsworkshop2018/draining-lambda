import json

from main.drain_container_instance import parse_event, get_container_instance_information, \
    prepare_complete_lifecycle_request, get_draining_operations, InstanceDrainingOperation, RetriggerLambdaOperation, \
    TerminateInstanceOperation


def test_parse_event():
    expected_event_body = {
        "LifecycleHookName": "asg-drain-before-terminate-hook-dev",
        "AccountId": "12345",
        "RequestId": "c49d901b-434f-451f-8238-29ec7add23c4",
        "LifecycleTransition": "autoscaling:EC2_INSTANCE_TERMINATING",
        "AutoScalingGroupName": "ecs-cluster-asg",
        "Service": "AWS Auto Scaling",
        "Time": "2018-08-31T22:07:11.513Z",
        "EC2InstanceId": "i-0d431729225fba8ce",
        "NotificationMetadata": {
            "cluster-name": "ecs-cluster-dev"
        },
        "LifecycleActionToken": "ac194dfe-b074-4f1c-937b-0002ae8177e3"
    }
    assert expected_event_body == parse_event(get_lambda_event())


def get_lambda_event():
    event = {
        "Records": [{
            "body": "{\r\n        \"LifecycleHookName\": \"asg-drain-before-terminate-hook-dev\",\r\n        "
                    "\"AccountId\": \"12345\",\r\n        \"RequestId\": "
                    "\"c49d901b-434f-451f-8238-29ec7add23c4\",\r\n        \"LifecycleTransition\": "
                    "\"autoscaling:EC2_INSTANCE_TERMINATING\",\r\n        \"AutoScalingGroupName\": "
                    "\"ecs-cluster-asg\",\r\n        "
                    "\"Service\": \"AWS Auto Scaling\",\r\n        \"Time\": \"2018-08-31T22:07:11.513Z\","
                    "\r\n        \"EC2InstanceId\": \"i-0d431729225fba8ce\",\r\n        \"NotificationMetadata\": "
                    "\"{\\r\\n    \\\"cluster-name\\\": \\\"ecs-cluster-dev\\\"\\r\\n}\",\r\n        "
                    "\"LifecycleActionToken\": \"ac194dfe-b074-4f1c-937b-0002ae8177e3\"\r\n }",
            "receiptHandle": "",
            "eventSourceARN": "arn:aws:sqs:us-east-1:12345:ecs-asg-drain-container-instances-lambda-events-queue-dev"
        }]
    }
    return event


def test_prepare_complete_lifecycle_action_request():
    event_body = {
        "LifecycleHookName": "asg-drain-before-terminate-hook-dev",
        "AccountId": "12345",
        "RequestId": "c49d901b-434f-451f-8238-29ec7add23c4",
        "LifecycleTransition": "autoscaling:EC2_INSTANCE_TERMINATING",
        "AutoScalingGroupName": "ecs-cluster-asg",
        "Service": "AWS Auto Scaling",
        "Time": "2018-08-31T22:07:11.513Z",
        "EC2InstanceId": "i-0c1b51d454cde95cd",
        "NotificationMetadata": "{\r\n    \"cluster-name\": \"ecs-cluster-dev\"\r\n}",
        "LifecycleActionToken": "ac194dfe-b074-4f1c-937b-0002ae8177e3"
    }
    expected_details = {
        "AutoScalingGroupName": "ecs-cluster-asg",
        "LifecycleActionResult": "CONTINUE",
        "LifecycleActionToken": "ac194dfe-b074-4f1c-937b-0002ae8177e3",
        "LifecycleHookName": "asg-drain-before-terminate-hook-dev",
        "InstanceId": "i-0c1b51d454cde95cd"
    }

    assert expected_details == prepare_complete_lifecycle_request(json.dumps(event_body))


def test_get_container_instance_information():
    container_instances_details = {
        "containerInstances": [
            {
                "containerInstanceArn": "arn:aws:ecs:us-east-1:12345:container-instance/71d70fc9-3235-4490-a475-"
                                        "cfbbfeb1f4e3",
                "status": "ACTIVE",
                "runningTasksCount": 1,
                "ec2InstanceId": "i-0c1b51d454cde95cd"
            }
        ]
    }
    assert ("arn:aws:ecs:us-east-1:12345:container-instance/71d70fc9-3235-4490-a475-cfbbfeb1f4e3", "ACTIVE", 1) \
           == get_container_instance_information("i-0c1b51d454cde95cd", container_instances_details)


def test_should_do_nothing_when_instance_does_not_exists():
    assert 0 == len(get_draining_operations(get_lambda_event(), None, None, None, 1))


def test_should_perform_some_operations_when_instance_exists():
    assert 0 != len(get_draining_operations(get_lambda_event(), None, "Container/ArnExists", None, 1))


def test_should_start_instance_draining_when_instance_in_not_in_draining_state():
    operations = get_draining_operations(get_lambda_event(), "clusterName",
                                         "arn:aws:ecs:us-east-1:12345:container-instance/"
                                         "71d70fc9-3235-4490-a475-cfbbfeb1f4e3", "ACTIVE", 1)
    assert 2 == len(operations)
    assert isinstance(operations[0], InstanceDrainingOperation)
    assert operations[0].cluster_name == "clusterName"
    assert operations[0].container_instance_id == "71d70fc9-3235-4490-a475-cfbbfeb1f4e3"


def test_should_retrigger_lambda_after_starting_draining():
    operations = get_draining_operations(get_lambda_event(), "clusterName",
                                         "arn:aws:ecs:us-east-1:12345:container-instance/"
                                         "71d70fc9-3235-4490-a475-cfbbfeb1f4e3", "ACTIVE", 1)
    assert 2 == len(operations)
    assert isinstance(operations[1], RetriggerLambdaOperation)
    assert operations[1].queue_name == "ecs-asg-drain-container-instances-lambda-events-queue-dev"
    assert operations[1].lambda_event == get_lambda_event()["Records"][0]["body"]


def test_should_retrigger_lambda_when_instance_in_draining_but_has_running_tasks():
    operations = get_draining_operations(get_lambda_event(), "clusterName",
                                         "arn:aws:ecs:us-east-1:12345:container-instance/"
                                         "71d70fc9-3235-4490-a475-cfbbfeb1f4e3",
                                         "DRAINING", 1)
    assert 1 == len(operations)
    assert isinstance(operations[0], RetriggerLambdaOperation)
    assert operations[0].queue_name == "ecs-asg-drain-container-instances-lambda-events-queue-dev"
    assert operations[0].lambda_event == get_lambda_event()["Records"][0]["body"]


def test_should_terminate_instance_when_instance_is_drained():
    operations = get_draining_operations(get_lambda_event(), "clusterName",
                                         "arn:aws:ecs:us-east-1:12345:container-instance/"
                                         "71d70fc9-3235-4490-a475-cfbbfeb1f4e3",
                                         "DRAINING", 0)
    assert 1 == len(operations)
    assert isinstance(operations[0], TerminateInstanceOperation)
    assert operations[0].complete_lifecyle_request == {
        "AutoScalingGroupName": "ecs-cluster-asg",
        "LifecycleActionResult": "CONTINUE",
        "LifecycleActionToken": "ac194dfe-b074-4f1c-937b-0002ae8177e3",
        "LifecycleHookName": "asg-drain-before-terminate-hook-dev",
        "InstanceId": "i-0d431729225fba8ce"
    }
