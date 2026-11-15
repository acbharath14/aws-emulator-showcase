# Order flow, provisioned with Terraform instead of boto3.
#
# This file provisions the same order flow the Python side builds in
# src/orderflow/pipeline.py: S3 holds the order document, SQS carries the
# order, Lambda validates it, DynamoDB stores the result, SNS notifies a
# second queue, CloudWatch observes it, and Step Functions orchestrates
# the processing step. Every name carries the var.prefix prefix, so this
# stack never collides with the pytest suite's per-test resources.

# S3: the order document bucket. force_destroy is on because this is
# an ephemeral demo stack: destroy removes the bucket even after a
# smoke check has written order documents into it.
resource "aws_s3_bucket" "orders" {
  bucket        = local.bucket_name
  force_destroy = true
}

# SQS: the order queue, and the queue SNS delivers notifications into.
resource "aws_sqs_queue" "orders" {
  name = local.queue_name
}

resource "aws_sqs_queue" "notify" {
  name = local.notify_queue
}

# SNS: the notification topic, its delivery into the notify queue, and
# the queue policy delivery needs. Without the policy, SNS accepts the
# publish and the message never arrives, the same as on real AWS.
resource "aws_sns_topic" "orders" {
  name = local.topic_name
}

resource "aws_sqs_queue_policy" "notify" {
  queue_url = aws_sqs_queue.notify.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.notify.arn
        Condition = {
          ArnEquals = { "aws:SourceArn" = aws_sns_topic.orders.arn }
        }
      }
    ]
  })
}

resource "aws_sns_topic_subscription" "notify" {
  topic_arn = aws_sns_topic.orders.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.notify.arn

  depends_on = [aws_sqs_queue_policy.notify]
}

# DynamoDB: the processed-orders table, on-demand billing, keyed by
# order_id. This mirrors store.create_orders_table.
resource "aws_dynamodb_table" "orders" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "order_id"

  attribute {
    name = "order_id"
    type = "S"
  }
}

# IAM: one role per service principal. The Lambda role is trusted by
# lambda.amazonaws.com; the Step Functions role is trusted by
# states.amazonaws.com and carries the lambda:InvokeFunction policy the
# emulator enforces on state machine executions. The Python side uses a
# single role with both trust statements; two roles say the same thing
# with each role holding only what its service needs.
resource "aws_iam_role" "lambda" {
  name = local.lambda_role

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role" "sfn" {
  name = local.sfn_role

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "states.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "sfn_invoke" {
  name = "invoke-function"
  role = aws_iam_role.sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.processor.arn
      }
    ]
  })
}

# Lambda: the order processor. The zip holds one file,
# lambda_function.py, whose content is src/orderflow/processor.py.
# This mirrors packaging.build_lambda_zip: the function runs the same
# code the tests exercise, not a copy.
data "archive_file" "processor" {
  type = "zip"

  source {
    content  = file("${path.module}/../src/orderflow/processor.py")
    filename = "lambda_function.py"
  }

  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "processor" {
  function_name    = local.function_name
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.processor.output_path
  source_code_hash = data.archive_file.processor.output_base64sha256
}

# Step Functions: the state machine that runs the processor Lambda with
# the execution input as its event. This mirrors
# workflow.processor_machine_definition.
resource "aws_sfn_state_machine" "orders" {
  name     = local.machine_name
  role_arn = aws_iam_role.sfn.arn

  definition = jsonencode({
    Comment = "Process one order with the order processor Lambda."
    StartAt = "ProcessOrder"
    States = {
      ProcessOrder = {
        Type     = "Task"
        Resource = aws_lambda_function.processor.arn
        End      = true
      }
    }
  })
}

# CloudWatch: the log group for processed orders, and an alarm on the
# OrdersProcessed metric in the OrderFlow namespace. The alarm fires
# when no order was processed in five minutes; missing data is treated
# as not breaching, so a quiet account does not page.
resource "aws_cloudwatch_log_group" "orders" {
  name = local.log_group
}

resource "aws_cloudwatch_metric_alarm" "orders_processed" {
  alarm_name          = "${var.prefix}-orders-processed"
  alarm_description   = "Fires when no order was processed in the last five minutes."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "OrdersProcessed"
  namespace           = "OrderFlow"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
}
