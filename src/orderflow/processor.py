"""Order processor: the Lambda handler.

Standard library only, so this file can be zipped on its own and run as a
Lambda function. It validates an order by recomputing its total from the
line items, which is real work: a stubbed runtime could not produce the
right answer for an arbitrary order.
"""

import json


def compute_total(items):
    total = 0
    for item in items:
        total += item["price"] * item["qty"]
    return total


def validate_order(event):
    order_id = event["order_id"]
    items = event.get("items", [])
    total = event.get("total")
    expected = compute_total(items)
    if total != expected:
        return {
            "order_id": order_id,
            "status": "rejected",
            "reason": "total mismatch",
            "expected": expected,
            "total": total,
        }
    return {
        "order_id": order_id,
        "status": "processed",
        "total": expected,
        "item_count": len(items),
    }


def handler(event, context):
    if isinstance(event, str):
        event = json.loads(event)
    return validate_order(event)
