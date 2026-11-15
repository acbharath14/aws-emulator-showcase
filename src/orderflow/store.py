"""Persistence: S3 holds order documents, DynamoDB holds processed orders."""

import json
import time


def create_bucket(s3, bucket):
    s3.create_bucket(Bucket=bucket)


def put_order_document(s3, bucket, order):
    """Store the order as JSON in S3 and return its key."""
    key = f"orders/{order['order_id']}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(order).encode())
    return key


def get_order_document(s3, bucket, key):
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    return json.loads(body)


def create_orders_table(dynamodb, table):
    dynamodb.create_table(
        TableName=table,
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    deadline = time.time() + 60
    while time.time() < deadline:
        status = dynamodb.describe_table(TableName=table)["Table"]["TableStatus"]
        if status == "ACTIVE":
            return
        time.sleep(1)
    raise TimeoutError(f"Table {table} never became ACTIVE")


def put_processed_order(dynamodb, table, result):
    dynamodb.put_item(
        TableName=table,
        Item={
            "order_id": {"S": result["order_id"]},
            "status": {"S": result["status"]},
            "total": {"N": str(result["total"])},
        },
    )


def get_processed_order(dynamodb, table, order_id):
    response = dynamodb.get_item(
        TableName=table, Key={"order_id": {"S": order_id}}
    )
    item = response.get("Item")
    if item is None:
        return None
    return {
        "order_id": item["order_id"]["S"],
        "status": item["status"]["S"],
        "total": int(item["total"]["N"]),
    }
