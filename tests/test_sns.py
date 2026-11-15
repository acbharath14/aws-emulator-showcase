"""SNS: notifications publish, and land in SQS when the policy allows."""

from orderflow import messaging


def test_publish_returns_message_id(clients, prefix):
    sns = clients["sns"]
    topic_arn = messaging.create_topic(sns, f"{prefix}-topic")
    message_id = messaging.publish_notification(sns, topic_arn, "hello")
    assert message_id


def test_publish_delivers_to_sqs(clients, prefix):
    sqs = clients["sqs"]
    sns = clients["sns"]
    topic_arn = messaging.create_topic(sns, f"{prefix}-topic")
    queue_url, queue_arn = messaging.create_order_queue(sqs, f"{prefix}-notify")
    messaging.allow_topic_to_queue(sqs, queue_url, queue_arn, topic_arn)
    messaging.subscribe_queue(sns, topic_arn, queue_arn)
    messaging.publish_notification(sns, topic_arn, "order order-1 processed")
    assert messaging.wait_for_notification(
        sqs, queue_url, "order order-1 processed"
    )
