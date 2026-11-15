# aws-emulator-showcase

An order-processing app that runs against AWS Emulator, the local AWS API
emulator, with no AWS account and no cloud spend. It shows AWS services
working together in tests: an order is stored in S3, queued in SQS,
processed by Lambda, recorded in DynamoDB, announced through SNS, and
observed with CloudWatch, with Step Functions orchestrating the processing
step.

## The order flow

1. An order document is written to S3.
2. The order is sent to an SQS queue and read back.
3. A Lambda function validates the order by recomputing its total.
4. The processed result is stored in DynamoDB and read back.
5. An SNS topic publishes a notification, delivered to an SQS queue.
6. CloudWatch records a metric and a log line for the order.

Step Functions runs the processing step as a Lambda task in the
state-machine path. The same flow also runs with a direct Lambda invoke,
so the two paths can be compared test by test.

## Prerequisites

- Python 3.12 or newer.
- AWS Emulator 1.0.385. Linux installs the native package; macOS and
  Windows run it in Docker. `scripts/preflight.py` checks for it and
  installs it on Linux when it can.
- No AWS account. No AWS credentials. The emulator generates dummy
  credentials per run, and they stop working when it stops.

## Quickstart

```
git clone https://github.com/acbharath14/aws-emulator-showcase.git
cd aws-emulator-showcase
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python scripts/preflight.py
.venv/bin/pytest
```

Preflight starts the emulator when it is not running, with telemetry off,
and waits until it answers. For an Allure report, run
`pytest --alluredir=allure-results` and open the results with the Allure
command line if it is installed. The suite has 25 tests, and all 25 passed
against emulator 1.0.385 in 24 seconds.

## What the emulator proves, and what it does not

For the operations this repo uses, the emulator returns the same results
and the same errors as AWS. A Lambda function runs real code: the
processor recomputes order totals, and a bad input returns a real Python
`TypeError` with a stack trace. Step Functions checks the execution role
the way AWS does: the role must trust `states.amazonaws.com` and carry a
policy allowing `lambda:InvokeFunction`, or the execution fails. SNS
delivery into SQS needs the usual queue policy, or the message never
arrives. The tests set all of this up the same way production code must.

What it does not prove:

- IAM and resource policies are not evaluated the way AWS evaluates them.
  Do not use this repo to test security settings.
- No throttling, no outages, no per-region behavior, no cross-account
  behavior.
- State lives in memory and is gone when the emulator stops. A restart
  starts from an empty account.
- Operations the emulator has not implemented fail with HTTP 501
  `NotImplemented` instead of succeeding silently.
- A passing suite here does not certify the same behavior on real AWS.
  Validate against real AWS before any production claim.

Fidelity scores for the services this repo uses, from the scores file in
the v1.0.385 release (scored 2026-11-14). A fidelity test can touch
several services, so the per-service totals overlap and do not add up to
the overall total. Scores move with each release; re-check them when the
pinned version changes.

| Service | Passed | Total | Share |
| --- | --- | --- | --- |
| S3 | 2061 | 2845 | 72.4% |
| SQS | 1190 | 1536 | 77.5% |
| Step Functions | 772 | 987 | 78.2% |
| Lambda | 1912 | 3021 | 63.3% |
| DynamoDB | 1542 | 2142 | 72.0% |
| SNS | 557 | 641 | 86.9% |
| CloudWatch | 974 | 1378 | 70.7% |
| CloudWatch Logs | 857 | 1235 | 69.4% |
| IAM | 830 | 1238 | 67.0% |
| STS | 163 | 261 | 62.5% |
| All services | 28505 | 43548 | 65.5% |

## Services covered

Exercised end to end: S3, SQS, DynamoDB, Lambda, Step Functions, SNS,
CloudWatch, CloudWatch Logs, IAM, STS.

API-shape only: ECS, Route 53, RDS. Their control-plane list calls answer
successfully with empty state, which is the part the emulator covers. No
container runs, no DNS zone resolves, no database engine starts. The
`tests/test_api_shape.py` file says this on every test.

## Layout

- `src/orderflow/`: the app. One module per concern: `config` resolves
  the emulator endpoint and credentials, `processor` is the Lambda
  handler, `packaging` builds its deployment zip, `store` covers S3 and
  DynamoDB, `messaging` covers SQS and SNS, `observe` covers CloudWatch,
  `iam_ops` and `lambda_ops` cover role and function setup, `workflow`
  covers Step Functions, `pipeline` runs the full order flow.
- `tests/`: pytest integration tests against the emulator, one behavior
  per test, negative cases included.
- `scripts/preflight.py`: checks Python, boto3, the emulator binary, and
  the running emulator. Installs the package on Linux when it can and
  starts the emulator with telemetry off.
- `terraform/`: the same order flow provisioned with Terraform instead of
  boto3. See the Terraform section below.
- `.github/workflows/ci.yml`: installs the emulator, starts it, runs the
  suite, uploads the Allure results. It holds no AWS credentials.

## Terraform

The `terraform/` directory provisions the same order flow as code: S3,
SQS, DynamoDB, Lambda, Step Functions, SNS, CloudWatch, and the two IAM
roles, all against the emulator, with no AWS account. The Lambda runs the
same `src/orderflow/processor.py` the tests exercise. Terraform 1.17.2
(the version this was verified with; `versions.tf` requires 1.17.x),
with the lock file pinning `hashicorp/aws` 6.73.0 and
`hashicorp/archive` 2.8.1. State is a local file, and the emulator
forgets everything on restart.

Usage, after preflight:

```
export SSL_CERT_FILE=$HOME/.aws/emulator/9297/ca.pem
export AWS_CA_BUNDLE=$HOME/.aws/emulator/9297/ca.pem
terraform -chdir=terraform init
terraform -chdir=terraform plan
terraform -chdir=terraform apply
terraform -chdir=terraform destroy
```

The `AWS_CA_BUNDLE` export is the part that bites. The emulator serves
HTTPS with a self-signed CA, and the AWS SDK for Go, which Terraform
uses, reads its trust bundle from that variable. Without it, every
provider call fails TLS verification and the SDK retries each call 25
times, so the command hangs for many minutes before failing. If your
shell already sets `AWS_CA_BUNDLE` to something else, override it to the
emulator CA for these commands. The full story, including the emulator
gaps found while building this, is in `terraform/README.md`.

## CI

The `ci` workflow runs on push and pull request to `main`, on
`ubuntu-24.04` with Python 3.12. It installs AWS Emulator 1.0.385 from
the LTS Debian package, starts it with telemetry off, installs the
pinned dependencies from `requirements.lock`, runs preflight in
check-only mode, then runs pytest with Allure results uploaded as an
artifact. A second job, `terraform`, runs after the test job: fmt check,
validate, plan, apply, a boto3 smoke check against the provisioned
stack, then destroy. The workflow file itself cannot be pushed through
the GitHub API; add it through the GitHub web UI when the repo is
created.

## Telemetry

AWS Emulator collects usage telemetry by default. This repo always
starts it with `--telemetry off` and `EMULATOR_TELEMETRY=off`, in
preflight and in CI, so nothing leaves the machine. The records AWS
collects never include request or response content, code, credentials,
or personal data, but off is the default here all the same.

## License

MIT. See `LICENSE`.
