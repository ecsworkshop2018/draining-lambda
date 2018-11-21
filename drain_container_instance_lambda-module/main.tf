
resource "aws_lambda_function" "drain_ecs_cluster_container_instances_lambda" {
  filename         = "drain_ecs_cluster_container_instances_lambda.zip"
  function_name    = "drain_ecs_cluster_container_instances_lambda_${var.env}"
  role             = "${aws_iam_role.iam_role_for_draining_container_instance_lambda.arn}"
  handler          = "drain_container_instance.lambda_handler"
  source_code_hash = "${var.source_code_hash}"
  runtime          = "python3.6"
  timeout          = 60

  tags = {
    Environment = "${var.env}"
    Name        = "drain_ecs_cluster_container_instances_lambda_${var.env}"
    CreatedBy   = "terraform"
  }

  environment {
    variables = {
      publish_events_message_queue_name = "${aws_sqs_queue.ecs_asg_drain_container_instances_lambda_events_queue.name}"
    }
  }
}

resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  batch_size        = 1
  event_source_arn  = "${aws_sqs_queue.ecs_asg_drain_container_instances_lambda_events_queue.arn}"
  enabled           = true
  function_name     = "${aws_lambda_function.drain_ecs_cluster_container_instances_lambda.function_name}"
}
