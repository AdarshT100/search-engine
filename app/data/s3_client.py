# Boto3 helper functions for uploading and deleting files in S3-compatible storage.
"""
app/data/s3_client.py
Boto3 helpers for uploading and deleting files in S3.
S3 keys are UUIDs — never user-supplied filenames.
"""
import uuid
from typing import BinaryIO
 
import boto3
from botocore.exceptions import ClientError
 
from app.core.config import get_settings
 
 
def _client():
    s = get_settings()
    return boto3.client(
        "s3",
        aws_access_key_id=s.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=s.AWS_SECRET_ACCESS_KEY,
        region_name=s.AWS_REGION,
    )
 
 
def upload_file(file_obj: BinaryIO, file_extension: str) -> str:
    """
    Upload a file-like object to S3.
    Returns the S3 key (UUID-based, not the original filename).
    Raises RuntimeError on S3 failure.
    """
    s3_key = f"uploads/{uuid.uuid4()}.{file_extension}"
    bucket = get_settings().S3_BUCKET_NAME
    try:
        _client().upload_fileobj(file_obj, bucket, s3_key)
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed: {e}") from e
    return s3_key
 
 
def delete_file(s3_key: str) -> None:
    """
    Delete a file from S3 by its key.
    Silently ignores 404 (already deleted).
    """
    bucket = get_settings().S3_BUCKET_NAME
    try:
        _client().delete_object(Bucket=bucket, Key=s3_key)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code != "NoSuchKey":
            raise RuntimeError(f"S3 delete failed: {e}") from e
