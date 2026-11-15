"""End to end: one order travels S3, SQS, Lambda, DynamoDB, SNS, CloudWatch."""

from orderflow import pipeline


def test_end_to_end_direct_lambda(clients, prefix, order):
    summary = pipeline.run_order_flow(clients, order, prefix)
    assert summary["result"]["status"] == "processed"
    assert summary["result"]["total"] == 25
    assert summary["saved"]["status"] == "processed"
    assert summary["saved"]["total"] == 25


def test_end_to_end_state_machine(clients, prefix, order):
    summary = pipeline.run_order_flow(clients, order, prefix, use_state_machine=True)
    assert summary["result"]["status"] == "processed"
    assert summary["result"]["total"] == 25
    assert summary["saved"]["status"] == "processed"
    assert summary["saved"]["total"] == 25
