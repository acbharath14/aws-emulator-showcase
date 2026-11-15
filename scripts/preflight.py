#!/usr/bin/env python3
"""Preflight: check the setup this repo needs, and fix what it can.

Checks, in order:
  1. Python 3.12 or newer.
  2. boto3 importable (the runtime dependency).
  3. The aws-emulator binary installed. On Linux, installs the LTS Debian
     package when run as root or with sudo available. On macOS, Docker is
     required and the Docker path is printed instead.
  4. The emulator running on the chosen port, with telemetry off. Starts
     it when it is not running.
  5. The emulator answering as its own account (000000000000).

Usage:
  python scripts/preflight.py            check, install, and start as needed
  python scripts/preflight.py --check-only
                                         check only, never install or start

Exit code is 0 when everything is ready, 1 otherwise. Every failure prints
the exact command that fixes it.
"""

import argparse
import os
import platform
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PINNED_VERSION = "1.0.385"
DEB_URLS = {
    "x86_64": "https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest/aws-emulator_amd64.deb",
    "aarch64": "https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest/aws-emulator_arm64.deb",
}
DOCKER_DOCS = "https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-docker.html"
DEFAULT_PORT = 9297


def fail(message, fix=None):
    print(f"FAIL: {message}")
    if fix:
        print(f"FIX: {fix}")
    sys.exit(1)


def ok(message):
    print(f"OK: {message}")


def check_python():
    if sys.version_info < (3, 12):
        fail(
            f"Python {sys.version_info.major}.{sys.version_info.minor} "
            "is too old; this repo needs 3.12 or newer.",
            "Install Python 3.12 or newer, then re-run preflight.",
        )
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")


def check_boto3():
    try:
        import boto3  # noqa: F401

        ok("boto3 importable")
    except ImportError:
        fail(
            "boto3 is not installed in this Python.",
            "python -m venv .venv && .venv/bin/pip install "
            "-r requirements.txt -r requirements-dev.txt",
        )


def install_emulator_linux():
    arch = platform.machine()
    url = DEB_URLS.get(arch)
    if url is None:
        fail(
            f"No Debian package known for processor {arch}.",
            "See https://docs.aws.amazon.com/emulator/latest/userguide/"
            "getting-started-linux.html for the package list.",
        )
    deb = Path.home() / f"aws-emulator-{PINNED_VERSION}.deb"
    print(f"Downloading the emulator package for {arch}...")
    try:
        urllib.request.urlretrieve(url, deb)
    except Exception as exc:  # noqa: BLE001 - report and stop
        fail(f"Could not download the emulator package: {exc}",
             f"Download it by hand: curl -fsSLo aws-emulator.deb {url}")
    if os.geteuid() == 0:
        cmd = ["dpkg", "-i", str(deb)]
    elif shutil.which("sudo"):
        cmd = ["sudo", "dpkg", "-i", str(deb)]
    else:
        fail(
            "Cannot install the emulator package without root or sudo.",
            f"sudo dpkg -i {deb}",
        )
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        fail(
            "The emulator package failed to install.",
            f"sudo apt-get install -y {deb}",
        )
    ok("Emulator package installed")


def check_emulator_binary():
    binary = shutil.which("aws-emulator")
    if binary:
        result = subprocess.run(
            ["aws-emulator", "-v"], capture_output=True, text=True
        )
        version = result.stdout.strip().splitlines()[0] if result.stdout else "?"
        ok(f"aws-emulator present ({version})")
        if PINNED_VERSION not in version:
            print(
                f"NOTE: this repo pins emulator {PINNED_VERSION}; "
                f"installed version is {version}. Fidelity scores in the "
                "README are for the pinned version."
            )
        return
    system = platform.system()
    if system == "Linux":
        print("aws-emulator is not installed. Installing the LTS package...")
        install_emulator_linux()
        if not shutil.which("aws-emulator"):
            fail("Install finished but aws-emulator is still not on PATH.",
                 "Check that /usr/bin is on PATH, then re-run preflight.")
    elif system == "Darwin":
        if not shutil.which("docker"):
            fail(
                "aws-emulator is not installed and Docker is missing.",
                "Install Docker Desktop, then follow the Docker path: "
                f"{DOCKER_DOCS}",
            )
        fail(
            "aws-emulator is not installed. On macOS it runs in Docker.",
            f"Follow the Docker path: {DOCKER_DOCS}",
        )
    else:
        fail(
            f"aws-emulator is not installed on {system}.",
            "See https://docs.aws.amazon.com/emulator/latest/userguide/"
            "getting-started.html for the install path.",
        )


def health_ok(port):
    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(
            f"https://127.0.0.1:{port}/__admin/health",
            timeout=5,
            context=context,
        ) as response:
            return response.read() == b"ok"
    except Exception:  # noqa: BLE001 - any failure means not ready
        return False


def start_emulator(port):
    log_dir = Path.home() / ".cache" / "aws-emulator-showcase"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"emulator-{port}.log"
    env = dict(os.environ, EMULATOR_TELEMETRY="off")
    with open(log_file, "ab") as log:
        subprocess.Popen(
            [
                "aws-emulator",
                "-p",
                str(port),
                "--telemetry",
                "off",
                "--idle-timeout",
                "1800",
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    deadline = time.time() + 60
    while time.time() < deadline:
        if health_ok(port):
            ok(f"Emulator running on port {port} (log: {log_file})")
            return
        time.sleep(1)
    fail(
        f"Emulator did not become healthy on port {port}.",
        f"Read the log: {log_file}",
    )


def check_emulator_running(port, check_only):
    if health_ok(port):
        ok(f"Emulator already running on port {port}")
        return
    if check_only:
        fail(
            f"Emulator is not running on port {port}.",
            "python scripts/preflight.py",
        )
    print(f"Emulator is not running on port {port}. Starting it...")
    start_emulator(port)


def check_identity(port):
    try:
        import boto3

        home = Path.home()
        creds_file = home / ".aws" / "emulator" / str(port) / "emulator_credentials"
        ca_bundle = home / ".aws" / "emulator" / str(port) / "ca.pem"
        import configparser

        parser = configparser.ConfigParser()
        parser.read(creds_file)
        sts = boto3.client(
            "sts",
            region_name="us-east-1",
            endpoint_url=f"https://127.0.0.1:{port}",
            aws_access_key_id=parser["default"]["aws_access_key_id"],
            aws_secret_access_key=parser["default"]["aws_secret_access_key"],
            verify=str(ca_bundle),
        )
        identity = sts.get_caller_identity()
        if identity["Account"] != "000000000000":
            fail(
                f"Unexpected account {identity['Account']}; "
                "requests are not reaching the emulator.",
                "Unset AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, "
                "AWS_SESSION_TOKEN, and AWS_PROFILE, then re-run preflight.",
            )
        ok("Emulator answers as account 000000000000")
    except ImportError:
        print("NOTE: boto3 missing, skipping the identity check.")
    except Exception as exc:  # noqa: BLE001 - report and stop
        fail(f"Could not confirm the emulator identity: {exc}",
             "Stop the emulator and re-run preflight.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="Check only; never install or start anything.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="Emulator port (default 9297).")
    args = parser.parse_args()

    check_python()
    check_boto3()
    check_emulator_binary()
    check_emulator_running(args.port, args.check_only)
    check_identity(args.port)
    print()
    print("Preflight passed. Run the suite with: pytest")
    print("Or with an Allure report: pytest --alluredir=allure-results")
    print()
    print("To point a shell at the emulator by hand:")
    print(f"  export AWS_ENDPOINT_URL=https://127.0.0.1:{args.port}")
    print("  export AWS_SHARED_CREDENTIALS_FILE="
          f"$HOME/.aws/emulator/{args.port}/emulator_credentials")
    print(f"  export AWS_CONFIG_FILE=$HOME/.aws/emulator/{args.port}/config")
    print(f"  export AWS_CA_BUNDLE=$HOME/.aws/emulator/{args.port}/ca.pem")
    print("  export AWS_EC2_METADATA_DISABLED=true")
    print("  export AWS_DISABLE_HOST_PREFIX_INJECTION=true")
    print("  export AWS_REGION=us-east-1")
    print("  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY "
          "AWS_SESSION_TOKEN AWS_PROFILE")


if __name__ == "__main__":
    main()
