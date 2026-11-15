"""IAM: the execution role and its policy are created and readable."""

import json

from orderflow import iam_ops


def as_document(value):
    """Parse a policy document that may arrive as JSON text or as a dict.

    Real AWS returns policy documents as JSON strings. The emulator returns
    them already parsed. Accept both, so the test asserts on the content
    either way.
    """
    if isinstance(value, dict):
        return value
    return json.loads(value)


def test_create_role_and_get_role(clients, prefix):
    iam = clients["iam"]
    role_arn = iam_ops.create_execution_role(iam, f"{prefix}-role")
    assert role_arn == f"arn:aws:iam::000000000000:role/{prefix}-role"
    role = iam.get_role(RoleName=f"{prefix}-role")["Role"]
    trust = as_document(role["AssumeRolePolicyDocument"])
    services = [s["Principal"]["Service"] for s in trust["Statement"]]
    assert "states.amazonaws.com" in services
    assert "lambda.amazonaws.com" in services


def test_put_role_policy_and_get_policy(clients, prefix):
    iam = clients["iam"]
    iam_ops.create_execution_role(iam, f"{prefix}-role")
    function_arn = f"arn:aws:lambda:us-east-1:000000000000:function:{prefix}-fn"
    iam_ops.attach_invoke_policy(iam, f"{prefix}-role", function_arn)
    policy = iam.get_role_policy(
        RoleName=f"{prefix}-role", PolicyName="invoke-function"
    )
    document = as_document(policy["PolicyDocument"])
    statement = document["Statement"][0]
    assert statement["Action"] == "lambda:InvokeFunction"
    assert statement["Resource"] == function_arn
