"""CloudWatch: metrics are accepted, log lines round-trip."""

from orderflow import observe


def test_put_metric_data_accepted(clients):
    clients["cloudwatch"].put_metric_data(
        Namespace="OrderFlow",
        MetricData=[{"MetricName": "OrdersProcessed", "Value": 1, "Unit": "Count"}],
    )


def test_logs_round_trip(clients, prefix):
    logs = clients["logs"]
    group = f"/orderflow/{prefix}"
    observe.write_log(logs, group, "run", "order order-1 processed")
    assert "order order-1 processed" in observe.read_log_messages(logs, group, "run")
