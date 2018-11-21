terraform {
  required_version = "= 0.11.10"

  backend "s3" {
    region     = "us-east-1"
    bucket     = "ecs-workshop-terraform-state-dev"
    key        = "ecs-workshop-cluster-draining-lambda-dev.tfstate"
    encrypt    = "true"
    dynamodb_table = "Terraform-Lock-Table"
  }
}

variable "env" {
  default = "dev"
}

provider "aws" {
  version = "~> 1.46"
  region  = "us-east-1"
}

provider "template" {
  version = "~> 1.0"
}

module "drain_container_instance" {
  source = "../drain_container_instance_lambda-module"
  env = "${var.env}"
  source_code_hash = "${base64sha256(file("drain_ecs_cluster_container_instances_lambda.zip"))}"
  ecs-asg-drain-container-instances-lambda-events-queue = "ecs-asg-drain-container-instances-lambda-events-queue-${var.env}"
  region = "us-east-1"
}
