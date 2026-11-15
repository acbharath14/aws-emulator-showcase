"""DynamoDB: processed orders are stored and read back."""

from orderflow import store


def test_put_and_get_item(clients, prefix):
    dynamodb = clients["dynamodb"]
    table = f"{prefix}-orders"
    store.create_orders_table(dynamodb, table)
    store.put_processed_order(
        dynamodb, table,
        {"order_id": "order-1", "status": "processed", "total": 25},
    )
    saved = store.get_processed_order(dynamodb, table, "order-1")
    assert saved == {"order_id": "order-1", "status": "processed", "total": 25}


def test_missing_item_returns_none(clients, prefix):
    dynamodb = clients["dynamodb"]
    table = f"{prefix}-orders"
    store.create_orders_table(dynamodb, table)
    assert store.get_processed_order(dynamodb, table, "no-such-order") is None
