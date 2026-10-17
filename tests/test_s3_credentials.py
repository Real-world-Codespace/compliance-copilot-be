from unittest.mock import sentinel

import boto3
import pytest

from app import storage


def test_s3_explicit_temporary_credentials_are_passed_to_boto3(monkeypatch):
    monkeypatch.setattr(storage, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage, "S3_REGION", "ap-southeast-1")
    monkeypatch.setattr(storage, "AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setattr(storage, "AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(storage, "AWS_SESSION_TOKEN", "test-token")
    calls = []
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: calls.append((args, kwargs)) or sentinel.client)

    assert storage.S3Storage().client is sentinel.client
    assert calls == [(('s3',), {
        "region_name": "ap-southeast-1", "aws_access_key_id": "test-key",
        "aws_secret_access_key": "test-secret", "aws_session_token": "test-token",
    })]


def test_s3_without_explicit_keys_uses_aws_credential_chain(monkeypatch):
    monkeypatch.setattr(storage, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage, "AWS_ACCESS_KEY_ID", "")
    monkeypatch.setattr(storage, "AWS_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(storage, "AWS_SESSION_TOKEN", "")
    calls = []
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: calls.append((args, kwargs)) or sentinel.client)

    assert storage.S3Storage().client is sentinel.client
    assert calls == [(('s3',), {"region_name": storage.S3_REGION})]


@pytest.mark.parametrize("access,secret,token", [
    ("test-key", "", ""), ("", "test-secret", ""), ("", "", "test-token"),
])
def test_s3_rejects_incomplete_explicit_credentials(monkeypatch, access, secret, token):
    monkeypatch.setattr(storage, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(storage, "AWS_ACCESS_KEY_ID", access)
    monkeypatch.setattr(storage, "AWS_SECRET_ACCESS_KEY", secret)
    monkeypatch.setattr(storage, "AWS_SESSION_TOKEN", token)
    with pytest.raises(RuntimeError, match="AWS_ACCESS_KEY_ID"):
        storage.S3Storage()
