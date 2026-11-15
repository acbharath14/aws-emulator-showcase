locals {
  # The emulator writes a fresh credentials file and CA bundle to
  # ~/.aws/emulator/<port>/ every time it starts. Terraform reads the
  # credentials from that file, so no key is ever written into this repo.
  # The file is regenerated on every emulator start, and Terraform reads
  # it fresh on every run, so a restart needs no config change.
  credentials_file = pathexpand("~/.aws/emulator/${var.emulator_port}/emulator_credentials")

  bucket_name   = "${var.prefix}-orders"
  queue_name    = "${var.prefix}-orders"
  notify_queue  = "${var.prefix}-notify"
  table_name    = "${var.prefix}-orders"
  topic_name    = "${var.prefix}-topic"
  function_name = "${var.prefix}-processor"
  lambda_role   = "${var.prefix}-lambda-role"
  sfn_role      = "${var.prefix}-sfn-role"
  machine_name  = "${var.prefix}-machine"
  log_group     = "/orderflow/${var.prefix}"
}

provider "aws" {
  region = var.region

  # Credentials come from the emulator's per-run file, not from this repo.
  # Fake static keys do not work: the emulator rejects them with
  # InvalidClientTokenId. Run scripts/preflight.py first so the file exists.
  shared_credentials_files = [local.credentials_file]
  profile                  = "default"

  # The emulator serves every service on one endpoint, so S3 must use
  # path-style addressing: a prefixed host such as data-127.0.0.1 does
  # not exist. This is the same reason the Python side sets
  # s3 addressing_style to path.
  s3_use_path_style = true

  # The emulator is not AWS. Do not let the provider probe it for
  # credentials, instance metadata, or the account id.
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
  skip_requesting_account_id  = true

  endpoints {
    s3            = var.emulator_endpoint
    sqs           = var.emulator_endpoint
    dynamodb      = var.emulator_endpoint
    lambda        = var.emulator_endpoint
    iam           = var.emulator_endpoint
    sts           = var.emulator_endpoint
    sns           = var.emulator_endpoint
    cloudwatch    = var.emulator_endpoint
    logs          = var.emulator_endpoint
    stepfunctions = var.emulator_endpoint
  }
}
