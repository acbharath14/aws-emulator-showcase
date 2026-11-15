"""Observability: CloudWatch metrics and logs for processed orders."""

import time


def put_order_metric(cloudwatch, count=1):
    """Record one processed order. PutMetricData returns nothing to check,
    so callers can only assert the call was accepted."""
    cloudwatch.put_metric_data(
        Namespace="OrderFlow",
        MetricData=[
            {"MetricName": "OrdersProcessed", "Value": count, "Unit": "Count"}
        ],
    )


def write_log(logs, group, stream, message):
    logs.create_log_group(logGroupName=group)
    logs.create_log_stream(logGroupName=group, logStreamName=stream)
    logs.put_log_events(
        logGroupName=group,
        logStreamName=stream,
        logEvents=[{"timestamp": int(time.time() * 1000), "message": message}],
    )


def read_log_messages(logs, group, stream):
    events = logs.get_log_events(
        logGroupName=group, logStreamName=stream
    )["events"]
    return [event["message"] for event in events]
