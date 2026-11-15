"""Lambda helpers: create, wait for Active, invoke.

A new function stays Pending until the runtime reports it Active. Invoking
during Pending raises ResourceConflictException on real AWS and on the
emulator, so callers must wait, as wait_for_active does.
"""

import json
import time


def create_processor_function(lambda_client, function_name, role_arn, zip_bytes):
    """Create the order processor function and return its ARN."""
    response = lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.12",
        Role=role_arn,
        Handler="lambda_function.handler",
        Code={"ZipFile": zip_bytes},
    )
    return response["FunctionArn"]


def wait_for_active(lambda_client, function_name, timeout=120):
    """Poll until the function reports Active, or raise TimeoutError."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = lambda_client.get_function_configuration(
            FunctionName=function_name
        ).get("State")
        if state == "Active":
            return True
        time.sleep(1)
    raise TimeoutError(f"Function {function_name} never became Active")


def invoke_processor(lambda_client, function_name, order):
    """Invoke the processor with an order and return the parsed payload.

    When the handler raises, the payload carries errorType and errorMessage
    instead of a result, and the response carries FunctionError. Callers
    that need to distinguish the two should check for "errorType" in the
    returned dict.
    """
    response = lambda_client.invoke(
        FunctionName=function_name, Payload=json.dumps(order)
    )
    return json.loads(response["Payload"].read())
