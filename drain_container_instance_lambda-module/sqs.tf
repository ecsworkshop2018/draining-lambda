data "aws_caller_identity" "aws_account" {}

resource "aws_sqs_queue" "ecs_asg_drain_container_instances_lambda_events_queue" {
  name = "${var.ecs-asg-drain-container-instances-lambda-events-queue}"
  visibility_timeout_seconds = 180
}

resource "aws_sqs_queue_policy" "ecs_asg_drain_container_instances_lambda_events_queue_policy" {
  queue_url = "${aws_sqs_queue.ecs_asg_drain_container_instances_lambda_events_queue.id}"

  policy =  <<POLICY
  {
    "Version": "2012-10-17",
    "Id": "${var.ecs-asg-drain-container-instances-lambda-events-queue}-policy",
    "Statement": [
      {
        "Sid": "AWSEvents_${var.ecs-asg-drain-container-instances-lambda-events-queue}",
        "Effect": "Allow",
        "Principal": {
          "Service": "events.amazonaws.com"
        },
        "Action": "sqs:SendMessage",
        "Resource": "${aws_sqs_queue.ecs_asg_drain_container_instances_lambda_events_queue.arn}",
        "Condition": {
        "StringLike": {
          "aws:SourceArn": "arn:aws:events:${var.region}:${data.aws_caller_identity.aws_account.account_id}:rule/*"
        }
      }
      }
    ]
  }
  POLICY
}
