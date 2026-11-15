"""Lambda: the processor runs real code and its errors are real errors."""

import json

import pytest
from botocore.exceptions import ClientError

from orderflow import lambda_ops, packaging


@pytest.fixture()
def function_name(clients, prefix, role_arn):
    name = f"{prefix}-processor"
    zip_bytes = packaging.build_lambda_zip()
    lambda_ops.create_processor_function(
        clients["lambda"], name, role_arn, zip_bytes
    )
    lambda_ops.wait_for_active(clients["lambda"], name)
    return name


def test_invoke_processes_valid_order(clients, function_name, order):
    result = lambda_ops.invoke_processor(clients["lambda"], function_name, order)
    assert result == {
        "order_id": "order-1",
        "status": "processed",
        "total": 25,
        "item_count": 2,
    }


def test_invoke_rejects_mismatched_total(clients, function_name, order):
    order["total"] = 999
    result = lambda_ops.invoke_processor(clients["lambda"], function_name, order)
    assert result["status"] == "rejected"
    assert result["reason"] == "total mismatch"
    assert result["expected"] == 25


def test_invoke_with_bad_input_returns_type_error(clients, function_name):
    # A string price reaches compute_total, where 0 + "ten" raises TypeError.
    response = clients["lambda"].invoke(
        FunctionName=function_name,
        Payload=json.dumps(
            {
                "order_id": "order-1",
                "items": [{"price": "ten", "qty": 1}],
                "total": 10,
            }
        ),
    )
    assert response.get("FunctionError") == "Unhandled"
    payload = json.loads(response["Payload"].read())
    assert payload["errorType"] == "TypeError"
    assert "lambda_function.py" in payload["stackTrace"][0]


def test_invoke_missing_function_raises_not_found(clients, prefix):
    with pytest.raises(ClientError) as exc:
        clients["lambda"].invoke(
            FunctionName=f"{prefix}-no-such-function", Payload=b"{}"
        )
    assert exc.value.response["Error"]["Code"] == "ResourceNotFoundException"
