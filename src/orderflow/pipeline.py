"""run_order_flow: the end-to-end order flow, driven step by step.

The steps, in order:
  1. S3: store the order document.
  2. SQS: queue the order, then read it back.
  3. Lambda: process the order, directly or through the state machine.
  4. DynamoDB: store the processed result, then read it back.
  5. SNS: publish a notification, and confirm it lands in a queue.
  6. CloudWatch: record a metric and write a log line.

Each step is a plain SDK call, so the flow reads the same on the emulator
and on real AWS. Returns a summary dict the tests assert on.
"""

from orderflow import iam_ops, lambda_ops, messaging, observe, packaging, store, workflow


def run_order_flow(clients, order, prefix, use_state_machine=False):
    s3 = clients["s3"]
    sqs = clients["sqs"]
    dynamodb = clients["dynamodb"]
    lambda_client = clients["lambda"]
    stepfunctions = clients["stepfunctions"]
    sns = clients["sns"]
    cloudwatch = clients["cloudwatch"]
    logs = clients["logs"]
    iam = clients["iam"]
    order_id = order["order_id"]

    bucket = f"{prefix}-orders"
    store.create_bucket(s3, bucket)
    key = store.put_order_document(s3, bucket, order)
    stored = store.get_order_document(s3, bucket, key)
    assert stored["order_id"] == order_id

    queue_url, _ = messaging.create_order_queue(sqs, f"{prefix}-orders")
    messaging.send_order(sqs, queue_url, order)
    received = messaging.receive_orders(sqs, queue_url)
    assert received and received[0]["order_id"] == order_id

    zip_bytes = packaging.build_lambda_zip()
    role_arn = iam_ops.create_execution_role(iam, f"{prefix}-role")
    function_arn = lambda_ops.create_processor_function(
        lambda_client, f"{prefix}-processor", role_arn, zip_bytes
    )
    lambda_ops.wait_for_active(lambda_client, f"{prefix}-processor")

    if use_state_machine:
        iam_ops.attach_invoke_policy(iam, f"{prefix}-role", function_arn)
        machine_arn = workflow.create_machine(
            stepfunctions,
            f"{prefix}-machine",
            workflow.processor_machine_definition(function_arn),
            role_arn,
        )
        status, result = workflow.start_and_wait(stepfunctions, machine_arn, order)
        assert status == "SUCCEEDED", f"machine failed: {status}"
    else:
        result = lambda_ops.invoke_processor(
            lambda_client, f"{prefix}-processor", received[0]
        )
    assert result["status"] == "processed", result

    table = f"{prefix}-orders"
    store.create_orders_table(dynamodb, table)
    store.put_processed_order(dynamodb, table, result)
    saved = store.get_processed_order(dynamodb, table, order_id)
    assert saved is not None and saved["total"] == order["total"]

    topic_arn = messaging.create_topic(sns, f"{prefix}-topic")
    notify_url, notify_arn = messaging.create_order_queue(sqs, f"{prefix}-notify")
    messaging.allow_topic_to_queue(sqs, notify_url, notify_arn, topic_arn)
    messaging.subscribe_queue(sns, topic_arn, notify_arn)
    messaging.publish_notification(
        sns, topic_arn, f"order {order_id} processed"
    )
    assert messaging.wait_for_notification(
        sqs, notify_url, f"order {order_id} processed"
    )

    observe.put_order_metric(cloudwatch)
    log_group = f"/orderflow/{prefix}"
    observe.write_log(logs, log_group, "run", f"order {order_id} processed")
    assert f"order {order_id} processed" in observe.read_log_messages(
        logs, log_group, "run"
    )

    return {
        "order_id": order_id,
        "bucket": bucket,
        "key": key,
        "queue_url": queue_url,
        "function_arn": function_arn,
        "result": result,
        "saved": saved,
        "table": table,
        "topic_arn": topic_arn,
    }
