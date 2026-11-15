"""S3: order documents are stored and read back, errors match AWS."""

import pytest
from botocore.exceptions import ClientError


def test_put_and_get_object(clients, prefix):
    s3 = clients["s3"]
    bucket = f"{prefix}-orders"
    s3.create_bucket(Bucket=bucket)
    s3.put_object(Bucket=bucket, Key="hello.txt", Body=b"hello emulator")
    body = s3.get_object(Bucket=bucket, Key="hello.txt")["Body"].read()
    assert body == b"hello emulator"


def test_list_buckets_shows_created_bucket(clients, prefix):
    s3 = clients["s3"]
    bucket = f"{prefix}-orders"
    s3.create_bucket(Bucket=bucket)
    names = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    assert bucket in names


def test_get_missing_key_raises_no_such_key(clients, prefix):
    s3 = clients["s3"]
    bucket = f"{prefix}-orders"
    s3.create_bucket(Bucket=bucket)
    with pytest.raises(ClientError) as exc:
        s3.get_object(Bucket=bucket, Key="missing.txt")
    assert exc.value.response["Error"]["Code"] == "NoSuchKey"


def test_get_from_missing_bucket_raises_no_such_bucket(clients, prefix):
    s3 = clients["s3"]
    with pytest.raises(ClientError) as exc:
        s3.get_object(Bucket=f"{prefix}-does-not-exist", Key="nope.txt")
    assert exc.value.response["Error"]["Code"] == "NoSuchBucket"
