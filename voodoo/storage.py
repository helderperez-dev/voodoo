import os
import aiofiles
import asyncio
from typing import Union

try:
    import boto3
    import botocore.config
except ImportError:
    boto3 = None

class StorageManager:
    def __init__(self):
        self.s3_bucket = os.getenv("VOODOO_S3_BUCKET")
        self.key = os.getenv("VOODOO_S3_KEY")
        self.secret = os.getenv("VOODOO_S3_SECRET")
        self.endpoint = os.getenv("VOODOO_S3_ENDPOINT")
        
        self.use_s3 = all([self.s3_bucket, self.key, self.secret, self.endpoint])
        
        if self.use_s3 and boto3:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.key,
                aws_secret_access_key=self.secret,
                endpoint_url=self.endpoint,
                config=botocore.config.Config(signature_version='s3v4')
            )
        else:
            self.s3_client = None

    @property
    def base_dir(self) -> str:
        try:
            return os.path.join(os.getcwd(), os.getenv("VOODOO_STORAGE_DIR", "storage"))
        except FileNotFoundError:
            return os.path.join(".", os.getenv("VOODOO_STORAGE_DIR", "storage"))

    def _get_local_path(self, bucket: str, path: str) -> str:
        """Helper to resolve the local file path for a specific bucket."""
        return os.path.join(self.base_dir, bucket, path)

    async def upload(self, file_content: Union[bytes, str], path: str, bucket: str = "public") -> str:
        """Uploads a file to a specific bucket and returns its path/url"""
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')
            
        if self.use_s3 and self.s3_client:
            s3_key = f"{bucket}/{path}"
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=file_content
            )
            return self.url(path, bucket)
        else:
            local_path = self._get_local_path(bucket, path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            async with aiofiles.open(local_path, 'wb') as f:
                await f.write(file_content)
            return self.url(path, bucket)

    async def delete(self, path: str, bucket: str = "public") -> bool:
        """Deletes a file from a specific bucket"""
        if self.use_s3 and self.s3_client:
            s3_key = f"{bucket}/{path}"
            await asyncio.to_thread(
                self.s3_client.delete_object,
                Bucket=self.s3_bucket,
                Key=s3_key
            )
            return True
        else:
            local_path = self._get_local_path(bucket, path)
            if os.path.exists(local_path):
                os.remove(local_path)
                return True
            return False

    def url(self, path: str, bucket: str = "public") -> str:
        """Returns the URL for a file in a specific bucket"""
        if self.use_s3 and self.s3_client:
            s3_key = f"{bucket}/{path}"
            if "amazonaws.com" in self.endpoint:
                return f"https://{self.s3_bucket}.s3.amazonaws.com/{s3_key}"
            return f"{self.endpoint}/{self.s3_bucket}/{s3_key}"
        else:
            return f"/storage/{bucket}/{path}"

storage = StorageManager()
