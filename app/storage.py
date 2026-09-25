"""Private S3 storage. ECS uses its task role through the standard AWS credential chain."""

from functools import lru_cache
from io import BytesIO

from .config import S3_BUCKET, S3_PRESIGNED_EXPIRY_SECONDS, S3_REGION


class S3Storage:
    def __init__(self) -> None:
        if not S3_BUCKET:
            raise RuntimeError("S3_BUCKET chưa được cấu hình.")
        import boto3
        self.client = boto3.client("s3", region_name=S3_REGION)

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


@lru_cache
def get_storage() -> S3Storage:
    return S3Storage()
