import logging
from io import BytesIO

import aioboto3

logger = logging.getLogger(__name__)


class S3StorageClient:
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ):
        self._endpoint_url = endpoint_url
        self._session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    async def ensure_bucket_exists(self, bucket: str) -> None:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            try:
                await s3.head_bucket(Bucket=bucket)
            except Exception:
                await s3.create_bucket(Bucket=bucket)
                logger.info(f"Created S3 bucket: {bucket}")

    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_data: bytes,
        content_type: str,
    ) -> str:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            await s3.upload_fileobj(
                BytesIO(file_data),
                bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        logger.info(f"Uploaded file to s3://{bucket}/{key}")
        return key

    async def generate_presigned_url(
        self, bucket: str, key: str, expires_in: int = 3600
    ) -> str:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        return url

    async def delete_file(self, bucket: str, key: str) -> None:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            await s3.delete_object(Bucket=bucket, Key=key)
        logger.info(f"Deleted file s3://{bucket}/{key}")
