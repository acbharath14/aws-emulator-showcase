"""SQS: orders are queued and read back."""

import json


def test_send_and_receive_message(clients, prefix):
    sqs = clients["sqs"]
    url = sqs.create_queue(QueueName=f"{prefix}-orders")["QueueUrl"]
    sqs.send_message(QueueUrl=url, MessageBody=json.dumps({"order_id": "order-1"}))
    messages = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=1).get("Messages", [])
    assert len(messages) == 1
    assert json.loads(messages[0]["Body"])["order_id"] == "order-1"


def test_queue_arn_looks_like_sqs(clients, prefix):
    sqs = clients["sqs"]
    url = sqs.create_queue(QueueName=f"{prefix}-orders")["QueueUrl"]
    arn = sqs.get_queue_attributes(
        QueueUrl=url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    assert arn.startswith("arn:aws:sqs:us-east-1:000000000000:")
