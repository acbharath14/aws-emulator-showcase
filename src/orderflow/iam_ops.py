"""IAM helpers: the execution role Step Functions needs.

On real AWS, a state machine that calls a Lambda function needs a role the
Step Functions service principal can assume, plus an identity-based policy
allowing lambda:InvokeFunction on that function. The emulator enforces the
same two checks, so the role is built exactly as it would be for AWS.
"""

import json

TRUST_DOCUMENT = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "states.amazonaws.com"},
            "Action": "sts:AssumeRole",
        },
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        },
    ],
}


def create_execution_role(iam, role_name):
    """Create the role and return its ARN."""
    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(TRUST_DOCUMENT),
    )
    return role["Role"]["Arn"]


def attach_invoke_policy(iam, role_name, function_arn):
    """Allow this role to invoke one Lambda function, and no other."""
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="invoke-function",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "lambda:InvokeFunction",
                        "Resource": function_arn,
                    }
                ],
            }
        ),
    )
