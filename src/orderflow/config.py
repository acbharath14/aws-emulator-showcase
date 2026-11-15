"""Connection settings for AWS Emulator.

The emulator writes a fresh access key, a config file, and a CA bundle to
``~/.aws/emulator/<port>/`` every time it starts. This module reads those
files, so the code never carries credentials of its own. No real AWS
credentials are used anywhere in this repo: the keys below are the
emulator's own per-run dummy keys, and they stop working when the emulator
stops.

Environment overrides:
  AWS_EMULATOR_PORT   Port the emulator serves on (default 9297).
  AWS_REGION          Region sent with every call (default us-east-1).
"""

import configparser
import os
from pathlib import Path

from botocore.config import Config

DEFAULT_PORT = 9297
DEFAULT_REGION = "us-east-1"


class EmulatorNotRunning(RuntimeError):
    """Raised when the emulator's per-run files are missing."""


def emulator_dir(port=None):
    """Directory holding this run's credentials, config, and CA bundle."""
    port = port or int(os.environ.get("AWS_EMULATOR_PORT", DEFAULT_PORT))
    return Path.home() / ".aws" / "emulator" / str(port), port


def endpoint_url(port=None):
    """HTTPS endpoint of the local emulator."""
    _, port = emulator_dir(port)
    return f"https://127.0.0.1:{port}"


def region():
    return os.environ.get("AWS_REGION", DEFAULT_REGION)


def load_credentials(port=None):
    """Read the emulator-generated access key for this run."""
    directory, port = emulator_dir(port)
    creds_file = directory / "emulator_credentials"
    if not creds_file.exists():
        raise EmulatorNotRunning(
            f"No emulator credentials at {creds_file}. "
            "Start the emulator first: python scripts/preflight.py"
        )
    parser = configparser.ConfigParser()
    parser.read(creds_file)
    return (
        parser["default"]["aws_access_key_id"],
        parser["default"]["aws_secret_access_key"],
        str(directory / "ca.pem"),
    )


def base_config():
    """Client config shared by every boto3 client in this repo.

    Host prefix injection is off because the emulator serves every service
    on one endpoint: a prefixed host such as data-127.0.0.1 does not exist.
    """
    return Config(inject_host_prefix=False, retries={"max_attempts": 2})


def make_client(service, session=None):
    """Build a boto3 client pointed at the local emulator."""
    import boto3

    key, secret, ca_bundle = load_credentials()
    kwargs = {"service_name": service, "region_name": region(),
              "endpoint_url": endpoint_url(),
              "aws_access_key_id": key, "aws_secret_access_key": secret,
              "verify": ca_bundle, "config": base_config()}
    if service == "s3":
        kwargs["config"] = Config(
            inject_host_prefix=False,
            retries={"max_attempts": 2},
            s3={"addressing_style": "path"},
        )
    if session is not None:
        return session.client(**kwargs)
    return boto3.client(**kwargs)
