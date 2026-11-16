# Terraform: the same order flow, provisioned as code

This directory provisions the same order flow the Python side builds in
`src/orderflow/pipeline.py`, using Terraform instead of boto3: an S3
bucket holds the order document, an SQS queue carries the order, a
Lambda function validates it, DynamoDB stores the result, an SNS topic
notifies a second queue, CloudWatch observes it, and Step Functions
orchestrates the processing step. The Lambda runs the same
`src/orderflow/processor.py` the tests exercise, zipped by the
`archive_file` data source the way `packaging.build_lambda_zip` zips it.

## What it proves, and what it does not

It proves the declarative half of the story: the architecture exists as
reviewable code, `terraform plan` shows the exact change before anything
happens, and a second run changes nothing. The provisioned stack runs
the same order through the same code as the pytest suite, and the smoke
check in CI proves it.

It does not prove anything about real AWS. Every call goes to the local
emulator, with the fidelity limits the main README lists. State is a
local file, and the emulator forgets everything on restart, so a restart
means `terraform apply` from an empty account. The two IAM roles hold
only what their service needs: the Lambda role is trusted by
`lambda.amazonaws.com`, the Step Functions role by
`states.amazonaws.com` with the `lambda:InvokeFunction` policy the
emulator enforces on executions.

## Prerequisites

- Terraform 1.17.2 (the version this was verified with; `versions.tf`
  requires 1.17.x). The lock file pins the providers:
  `hashicorp/aws` 6.73.0, `hashicorp/archive` 2.8.1.
- The emulator running. Run `python scripts/preflight.py` from the repo
  root first. It starts the emulator and prints the export block below.
- No AWS account. The credentials come from the emulator's per-run file
  at `~/.aws/emulator/9297/emulator_credentials`, which the provider
  reads on every run. Fake static keys do not work: the emulator rejects
  them with `InvalidClientTokenId`.

## Usage

Run these from the repo root, after preflight. The two certificate
exports are not optional. The emulator serves HTTPS with a self-signed
CA, and the AWS SDK for Go, which Terraform uses, reads its trust bundle
from `AWS_CA_BUNDLE`. Without it, every provider call fails TLS
verification with `certificate signed by unknown authority`, and the SDK
retries each call 25 times with backoff, so the command hangs for many
minutes before failing. Point `AWS_CA_BUNDLE` at the emulator's per-run
CA file. Preflight prints this export already. If `AWS_CA_BUNDLE` is set
to something else in your shell, for example an egress proxy bundle, it
must be overridden to the emulator CA for these commands.

```
export SSL_CERT_FILE=$HOME/.aws/emulator/9297/ca.pem
export AWS_CA_BUNDLE=$HOME/.aws/emulator/9297/ca.pem
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan
terraform -chdir=terraform apply
terraform -chdir=terraform destroy
```

`plan` creates 14 resources. `apply` takes about a minute, most of it
the SQS waits. Prove the stack works with the smoke check, which runs
one order through every provisioned resource:

```
PYTHONPATH=src .venv/bin/python scripts/terraform_smoke.py
```

`destroy` takes about a minute too, again mostly SQS. The S3 bucket
carries `force_destroy`, so destroy removes the bucket even after a
smoke check has written order documents into it. All resource names
carry the `tf-` prefix by default (`var.prefix`), so this stack never
collides with the pytest suite's per-test resources.

## Layout

- `versions.tf`: pinned Terraform and provider versions.
- `variables.tf`: prefix, region, emulator endpoint and port.
- `providers.tf`: the AWS provider pointed at the emulator, with the
  per-service endpoints, the path-style S3 setting, and the skip flags
  that stop the provider probing for real AWS credentials, metadata, or
  the account id.
- `main.tf`: the resources. One file, no modules, one stack.
- `outputs.tf`: bucket, queues, table, topic, function, state machine,
  log group.
- `.terraform.lock.hcl`: the pinned provider selections. Commit it.

## Emulator gaps found while building this

- `AWS_CA_BUNDLE` is the variable that decides TLS trust for Terraform,
  not `SSL_CERT_FILE`. See Usage above. The failure mode is a hang, not
  an error, because the SDK retries each failed call 25 times.
- Re-creating an existing SQS queue with `CreateQueue` and no attributes
  fails on the emulator with `QueueAlreadyExists` when the queue's
  attributes differ from the emulator's assumed defaults. Real AWS
  returns the existing queue. The smoke check looks existing queues up
  with `get_queue_url` instead.
- One `terraform destroy` failed with `BucketNotEmpty` even though the
  bucket carried `force_destroy` and the object was then deleted by the
  retry. The identical destroy run immediately after completed with all
  14 resources destroyed. Treat a lone `BucketNotEmpty` on destroy as a
  transient emulator inconsistency and re-run destroy before
  investigating further.
- SQS create and destroy are slow against the emulator, about 25 seconds
  per queue on create and about 42 seconds per queue on destroy. The
  calls succeed; the provider polls with long intervals.
