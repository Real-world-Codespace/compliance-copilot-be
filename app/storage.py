"""Private S3 storage. ECS uses its task role through the standard AWS credential chain."""

from functools import lru_cache
from io import BytesIO

from .config import (
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, ENVIRONMENT,
    LOCAL_STORAGE_DIR, S3_BUCKET, S3_PRESIGNED_EXPIRY_SECONDS, S3_REGION, STORAGE_BACKEND,
)


class S3Storage:
    def __init__(self) -> None:
        if not S3_BUCKET:
            raise RuntimeError("S3_BUCKET chưa được cấu hình.")
        if bool(AWS_ACCESS_KEY_ID) != bool(AWS_SECRET_ACCESS_KEY) or (AWS_SESSION_TOKEN and not AWS_ACCESS_KEY_ID):
            raise RuntimeError("Cần cấu hình đầy đủ AWS_ACCESS_KEY_ID và AWS_SECRET_ACCESS_KEY.")
        import boto3
        credentials = {}
        if AWS_ACCESS_KEY_ID:
            credentials = {"aws_access_key_id": AWS_ACCESS_KEY_ID, "aws_secret_access_key": AWS_SECRET_ACCESS_KEY}
            if AWS_SESSION_TOKEN:
                credentials["aws_session_token"] = AWS_SESSION_TOKEN
        self.client = boto3.client("s3", region_name=S3_REGION, **credentials)

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.client.upload_fileobj(
            BytesIO(data), S3_BUCKET, key,
            ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "aws:kms"},
        )

    def download(self, key: str) -> bytes:
        return self.client.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()

    def download_url(self, key: str, filename: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key, "ResponseContentDisposition": f'attachment; filename="{filename}"'},
            ExpiresIn=S3_PRESIGNED_EXPIRY_SECONDS,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=S3_BUCKET, Key=key)


class LocalStorage:
    """Local development only; files are private and never served by the web server."""
    def _path(self, key: str):
        root = LOCAL_STORAGE_DIR.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Invalid storage key")
        return path

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def download(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


@lru_cache
def get_storage() -> S3Storage | LocalStorage:
    if STORAGE_BACKEND == "s3":
        return S3Storage()
    if STORAGE_BACKEND == "local" and ENVIRONMENT != "production":
        return LocalStorage()
    raise RuntimeError("Production requires STORAGE_BACKEND=s3; local storage is development-only.")
