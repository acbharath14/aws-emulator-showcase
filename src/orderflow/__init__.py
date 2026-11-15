"""Order flow: an order-processing app that runs against AWS Emulator.

Every call in this package goes to the local emulator, never to real AWS.
See config.py for how the endpoint and credentials are resolved.
"""

__all__ = [
    "config",
    "processor",
    "packaging",
    "iam_ops",
    "lambda_ops",
    "store",
    "messaging",
    "observe",
    "workflow",
    "pipeline",
]
