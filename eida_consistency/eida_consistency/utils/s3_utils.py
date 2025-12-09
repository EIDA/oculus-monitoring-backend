"""
Utilities for uploading reports to the Resif S3 (MinIO) bucket.
"""

import os
import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def get_s3_client():
    """
    Create an S3 client configured for the Resif staging MinIO server.

    Credentials must be provided via environment variables:
      - EIDA_S3_KEY
      - EIDA_S3_SECRET
    """
    key = os.getenv("EIDA_S3_KEY")
    secret = os.getenv("EIDA_S3_SECRET")

    if not key or not secret:
        logger.warning("S3 credentials not set (EIDA_S3_KEY / EIDA_S3_SECRET).")
        return None

    try:
        return boto3.client(
            "s3",
            endpoint_url="https://s3-staging.resif.fr:443",
            aws_access_key_id=key,
            aws_secret_access_key=secret,
            verify=False,  # staging uses a self-signed certificate
        )
    except Exception as e:
        logger.error("Failed to create S3 client: %s", e)
        return None


def upload_report(report_path: str, bucket: str = "eida", prefix: str = "reports") -> str | None:
    """
    Upload a report file to the S3 bucket and return the public URL.

    Parameters
    ----------
    report_path : str
        Path to the local report file to upload.
    bucket : str, optional
        Name of the S3 bucket (default: "eida").
    prefix : str, optional
        Folder/prefix inside the bucket (default: "reports").

    Returns
    -------
    str | None
        Public URL of the uploaded report, or None if upload failed.
    """
    s3 = get_s3_client()
    if s3 is None:
        return None

    filename = os.path.basename(report_path)
    key = f"{prefix}/{filename}"

    try:
        s3.upload_file(report_path, bucket, key, ExtraArgs={"ACL": "public-read"})
        url = f"http://eida.s3-staging.resif.fr/{key}"
        return url
    except (BotoCoreError, ClientError, OSError) as e:
        logger.error("Failed to upload report to S3: %s", e)
        return None
