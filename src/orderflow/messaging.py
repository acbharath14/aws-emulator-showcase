"""Messaging: SQS carries orders, SNS notifies when one is processed."""

import json
import time


def create_order_queue(sqs, name):
    """Create the queue and return (queue_url, queue_arn)."""
    url = sqs.create_queue(QueueName=name)["QueueUrl"]
    arn = sqs.get_queue_attributes(
        QueueUrl=url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    return url, arn


def send_order(sqs, queue_url, order):
    return sqs.send_message(
        QueueUrl=queue_url, MessageBody=json.dumps(order)
    )["MessageId"]


def receive_orders(sqs, queue_url, max_messages=10, wait_seconds=1):
    """Receive messages and return their parsed JSON bodies."""
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_seconds,
    )
    return [json.loads(m["Body"]) for m in response.get("Messages", [])]


def create_topic(sns, name):
    return sns.create_topic(Name=name)["TopicArn"]


def allow_topic_to_queue(sqs, queue_url, queue_arn, topic_arn):
    """Attach the queue policy SNS needs to deliver into SQS.

    Without this policy, SNS accepts the publish and the message never
    arrives. That matches real AWS: the policy is part of the setup, not
    an emulator quirk.
    """
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
                "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
            }
        ],
    }
    sqs.set_queue_attributes(
        QueueUrl=queue_url, Attributes={"Policy": json.dumps(policy)}
    )


def subscribe_queue(sns, topic_arn, queue_arn):
    return sns.subscribe(
        TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn
    )["SubscriptionArn"]


def publish_notification(sns, topic_arn, message):
    return sns.publish(TopicArn=topic_arn, Message=message)["MessageId"]


def wait_for_notification(sqs, queue_url, text, timeout=15):
    """Poll the queue until a message containing text arrives."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=1
        )
        for message in response.get("Messages", []):
            if text in message["Body"]:
                return True
        time.sleep(1)
    return False
