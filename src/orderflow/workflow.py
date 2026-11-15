"""Step Functions: the order-processing state machine.

The machine has one task: run the order processor Lambda with the execution
input as its event, and finish with the Lambda's result as the output.
"""

import json
import time


def processor_machine_definition(function_arn):
    return {
        "Comment": "Process one order with the order processor Lambda.",
        "StartAt": "ProcessOrder",
        "States": {
            "ProcessOrder": {
                "Type": "Task",
                "Resource": function_arn,
                "End": True,
            }
        },
    }


def pass_machine_definition():
    return {
        "Comment": "No-op machine used to prove executions run to completion.",
        "StartAt": "Hello",
        "States": {
            "Hello": {"Type": "Pass", "Result": {"ok": True}, "End": True}
        },
    }


def create_machine(stepfunctions, name, definition, role_arn):
    return stepfunctions.create_state_machine(
        name=name,
        definition=json.dumps(definition),
        roleArn=role_arn,
    )["stateMachineArn"]


def start_and_wait(stepfunctions, machine_arn, order, timeout=120):
    """Start an execution and wait for a terminal status.

    Returns (status, output_dict). Output is empty when the execution
    failed; callers that need the failure cause should call
    describe_execution themselves.
    """
    execution_arn = stepfunctions.start_execution(
        stateMachineArn=machine_arn, input=json.dumps(order)
    )["executionArn"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        execution = stepfunctions.describe_execution(executionArn=execution_arn)
        status = execution["status"]
        if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            output = execution.get("output", "")
            return status, json.loads(output) if output else {}
        time.sleep(1)
    raise TimeoutError(f"Execution {execution_arn} never reached a terminal status")
