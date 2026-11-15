"""Shared fixtures: an emulator that must be running, boto3 clients, names.

Run scripts/preflight.py first if the emulator is not up; these fixtures
fail with that instruction instead of a confusing connection error.
"""

import ssl
import urllib.request
import uuid

import pytest

from orderflow import config

SERVICES = [
    "s3",
    "sqs",
    "dynamodb",
    "lambda",
    "stepfunctions",
    "sns",
    "cloudwatch",
    "logs",
    "iam",
    "sts",
    "ecs",
    "route53",
    "rds",
]


@pytest.fixture(scope="session")
def emulator():
    """Confirm the emulator answers, or fail with the fix."""
    try:
        _, _, ca_bundle = config.load_credentials()
    except config.EmulatorNotRunning as exc:
        pytest.fail(str(exc))
    context = ssl.create_default_context(cafile=ca_bundle)
    try:
        with urllib.request.urlopen(
            config.endpoint_url() + "/__admin/health",
            timeout=5,
            context=context,
        ) as response:
            assert response.read() == b"ok"
    except Exception as exc:  # noqa: BLE001 - any failure means not ready
        pytest.fail(
            f"AWS Emulator is not answering at {config.endpoint_url()}: {exc}. "
            "Start it with: python scripts/preflight.py"
        )
    return True


@pytest.fixture(scope="session")
def clients(emulator):  # noqa: ARG001 - session guard
    return {name: config.make_client(name) for name in SERVICES}


@pytest.fixture()
def prefix():
    """Unique resource prefix per test, so tests never share state."""
    return f"t{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def order():
    """A valid order: 2 x 10 plus 1 x 5, total 25."""
    return {
        "order_id": "order-1",
        "items": [
            {"price": 10, "qty": 2},
            {"price": 5, "qty": 1},
        ],
        "total": 25,
    }


@pytest.fixture()
def role_arn():
    """A role ARN string for calls that only need a role to exist on paper.

    Direct Lambda invokes accept any well-formed ARN. The Step Functions
    tests build a real role instead; see test_stepfunctions.py.
    """
    return "arn:aws:iam::000000000000:role/orderflow-test-role"
