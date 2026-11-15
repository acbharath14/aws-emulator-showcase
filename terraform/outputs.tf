output "bucket_name" {
  description = "S3 bucket holding order documents."
  value       = aws_s3_bucket.orders.bucket
}

output "queue_url" {
  description = "SQS queue carrying orders."
  value       = aws_sqs_queue.orders.url
}

output "notify_queue_url" {
  description = "SQS queue receiving SNS notifications."
  value       = aws_sqs_queue.notify.url
}

output "table_name" {
  description = "DynamoDB table holding processed orders."
  value       = aws_dynamodb_table.orders.name
}

output "topic_arn" {
  description = "SNS topic announcing processed orders."
  value       = aws_sns_topic.orders.arn
}

output "function_arn" {
  description = "Lambda function validating orders."
  value       = aws_lambda_function.processor.arn
}

output "state_machine_arn" {
  description = "Step Functions state machine processing orders."
  value       = aws_sfn_state_machine.orders.arn
}

output "log_group_name" {
  description = "CloudWatch log group for processed orders."
  value       = aws_cloudwatch_log_group.orders.name
}
