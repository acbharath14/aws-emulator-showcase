#!/usr/bin/env python3
"""Smoke check the Terraform-provisioned stack.

Runs one order through every resource the terraform/ stack creates:
S3, SQS, Lambda, Step Functions, DynamoDB, SNS, and CloudWatch. It
uses the repo's own helpers, the same code the pytest suite exercises,
so a passing check means the provisioned stack behaves the way the
tests expect.

Run it after terraform apply, from the repo root:

  PYTHONPATH=src python scripts/terraform_smoke.py [--prefix tf]

Exit code is 0 when every check passes, 1 otherwise. It writes one
order document, one queue message, one table item, and one notification,
all of which terraform destroy removes with the stack.
"""

import argparse

from orderflow import config, lambda_ops, messaging, observe, store, workflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="tf",
                        help="Resource prefix the stack was applied with.")
    args = parser.parse_args()
    prefix = args.prefix

    clients = {name: config.make_client(name) for name in
               ("s3", "sqs", "dynamodb", "lambda", "stepfunctions",
                "sns", "cloudwatch", "logs", "iam")}
    order = {"order_id": "order-1",
             "items": [{"price": 10, "qty": 2}, {"price": 5, "qty": 1}],
             "total": 25}

    store.put_order_document(clients["s3"], f"{prefix}-orders", order)
    stored = store.get_order_document(
        clients["s3"], f"{prefix}-orders", "orders/order-1.json")
    assert stored == order, stored
    print("1. S3 put/get: OK")

    # Look the queue up instead of creating it: the emulator rejects
    # CreateQueue on an existing queue when the attributes are not
    # repeated exactly, where real AWS returns the existing queue.
    queue_url = clients["sqs"].get_queue_url(
        QueueName=f"{prefix}-orders")["QueueUrl"]
    messaging.send_order(clients["sqs"], queue_url, order)
    received = messaging.receive_orders(clients["sqs"], queue_url)
    assert received and received[0]["order_id"] == "order-1", received
    print("2. SQS send/receive: OK")

    result = lambda_ops.invoke_processor(
        clients["lambda"], f"{prefix}-processor", order)
    assert result["status"] == "processed", result
    assert result["total"] == 25, result
    print(f"3. Lambda invoke: OK ({result})")

    machine = ("arn:aws:states:us-east-1:000000000000:"
               f"stateMachine:{prefix}-machine")
    status, output = workflow.start_and_wait(
        clients["stepfunctions"], machine, order)
    assert status == "SUCCEEDED", status
    assert output["status"] == "processed", output
    print(f"4. Step Functions execution: OK ({status})")

    store.put_processed_order(clients["dynamodb"], f"{prefix}-orders", result)
    saved = store.get_processed_order(
        clients["dynamodb"], f"{prefix}-orders", "order-1")
    assert saved is not None and saved["total"] == 25, saved
    print(f"5. DynamoDB put/get: OK ({saved})")

    notify_url = clients["sqs"].get_queue_url(
        QueueName=f"{prefix}-notify")["QueueUrl"]
    topic = clients["sns"].create_topic(
        Name=f"{prefix}-topic")["TopicArn"]
    messaging.publish_notification(
        clients["sns"], topic, "order order-1 processed")
    assert messaging.wait_for_notification(
        clients["sqs"], notify_url, "order order-1 processed")
    print("6. SNS publish delivered to notify queue: OK")

    observe.put_order_metric(clients["cloudwatch"])
    alarms = clients["cloudwatch"].describe_alarms(
        AlarmNames=[f"{prefix}-orders-processed"])["MetricAlarms"]
    assert len(alarms) == 1, alarms
    print("7. CloudWatch alarm exists:",
          alarms[0]["AlarmName"], "state:", alarms[0]["StateValue"])
    groups = clients["logs"].describe_log_groups(
        logGroupNamePrefix=f"/orderflow/{prefix}")["logGroups"]
    assert any(g["logGroupName"] == f"/orderflow/{prefix}"
               for g in groups), groups
    print("8. CloudWatch log group exists: OK")

    print("Terraform smoke check passed.")


if __name__ == "__main__":
    main()
