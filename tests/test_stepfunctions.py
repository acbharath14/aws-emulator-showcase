"""Step Functions: executions run to completion, including a Lambda task.

The Lambda-task test is the strictest one in the repo: the machine only
succeeds when the execution role trusts states.amazonaws.com and carries an
identity policy allowing lambda:InvokeFunction on the function. Both checks
mirror real AWS.
"""

import pytest

from orderflow import iam_ops, lambda_ops, packaging, workflow


@pytest.fixture()
def processor(clients, prefix, role_arn):
    name = f"{prefix}-processor"
    zip_bytes = packaging.build_lambda_zip()
    function_arn = lambda_ops.create_processor_function(
        clients["lambda"], name, role_arn, zip_bytes
    )
    lambda_ops.wait_for_active(clients["lambda"], name)
    return function_arn


def test_pass_machine_succeeds(clients, prefix, role_arn):
    stepfunctions = clients["stepfunctions"]
    machine_arn = workflow.create_machine(
        stepfunctions,
        f"{prefix}-pass",
        workflow.pass_machine_definition(),
        role_arn,
    )
    status, output = workflow.start_and_wait(stepfunctions, machine_arn, {})
    assert status == "SUCCEEDED"
    assert output == {"ok": True}


def test_lambda_task_machine_succeeds(clients, prefix, processor, order):
    iam = clients["iam"]
    stepfunctions = clients["stepfunctions"]
    role_name = f"{prefix}-role"
    role_arn = iam_ops.create_execution_role(iam, role_name)
    iam_ops.attach_invoke_policy(iam, role_name, processor)
    machine_arn = workflow.create_machine(
        stepfunctions,
        f"{prefix}-machine",
        workflow.processor_machine_definition(processor),
        role_arn,
    )
    status, output = workflow.start_and_wait(stepfunctions, machine_arn, order)
    assert status == "SUCCEEDED"
    assert output["status"] == "processed"
    assert output["total"] == 25
