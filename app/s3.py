import os
from pathlib import Path
import base64
import hashlib
from typing import BinaryIO

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.client import Config, BaseClient


def _make_s3_client() -> BaseClient:
    s3_endpoint = os.environ.get("S3_ENDPOINT")
    return boto3.client(
        "s3", endpoint_url=s3_endpoint, config=Config(signature_version="s3v4")
    )


def _read_sse_key() -> bytes:
    key_path = os.environ.get("SECRET_KEY_BIN")
    if not key_path:
        raise RuntimeError("SECRET_KEY_BIN environment variable is not set")
    p = Path(key_path)
    if not p.exists():
        raise RuntimeError(f"SSE key file not found: {key_path}")
    data = p.read_bytes()
    if len(data) != 32:
        raise RuntimeError(f"SSE key length invalid: got {len(data)} bytes 32")
    return data


def _sse_args_from_key(key: bytes) -> dict[str, str]:
    key_b64 = base64.b64encode(key).decode("utf-8")
    key_md5_b64 = base64.b64encode(hashlib.md5(key).digest()).decode("utf-8")
    return {
        "SSECustomerAlgorithm": "AES256",
        "SSECustomerKey": key_b64,
        "SSECustomerKeyMD5": key_md5_b64,
    }


def download_object(object_key: str):
    """
    Returns the boto3 response for get_object (including 'Body' = StreamingBody).
    If the object is crypted using SSE-C, the SECRET_KEY_BIN key is read and SSE-C headers are used.
    Raises ClientError or RuntimeError in case of error.
    """
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET environment variable is not set")

    client = _make_s3_client()

    key = _read_sse_key()
    kwargs = _sse_args_from_key(key)

    resp = client.get_object(Bucket=bucket, Key=object_key, **kwargs)
    return resp


def upload_object(object_key: str, file: BinaryIO):

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET environment variable is not set")

    client = _make_s3_client()

    key = _read_sse_key()
    kwargs = _sse_args_from_key(key)

    if hasattr(file, "seek"):
        file.seek(0)

    transfer_config = TransferConfig(
        multipart_threshold=50 * 1024 * 1024,  # 50 MB
        max_concurrency=10,
        multipart_chunksize=50 * 1024 * 1024,
    )

    client.upload_fileobj(
        file, bucket, object_key, ExtraArgs=kwargs, Config=transfer_config
    )


def delete_object(object_key: str):
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET environment variable is not set")

    client = _make_s3_client()

    client.delete_object(Bucket=bucket, Key=object_key)
    client.close()


def delete_objects(object_keys: list[str]):
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET environment variable is not set")

    client = _make_s3_client()

    for i in range(0, len(object_keys), 1000):
        batch = [{"Key": k} for k in object_keys[i : i + 1000]]
        client.delete_objects(Bucket=bucket, Delete={"Objects": batch})

    client.close()
