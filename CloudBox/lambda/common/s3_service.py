"""S3 operations; credentials come from the Lambda execution role."""

import os

_S3_CLIENT = None

def _client():
    global _S3_CLIENT
    if _S3_CLIENT is not None:
        return _S3_CLIENT
    from botocore.config import Config

    # The managed Lambda runtime includes boto3. Import lazily so local unit
    # tests can replace this service without installing the full AWS SDK.
    import boto3

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    _S3_CLIENT = boto3.client(
        "s3",
        region_name=region,
        config=Config(signature_version="s3v4"),
    )
    return _S3_CLIENT


def create_upload_url(s3_key, content_type, content_length):
    return _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": os.environ["S3_BUCKET_NAME"],
            "Key": s3_key,
            "ContentType": content_type,
            "ContentLength": content_length,
        },
        ExpiresIn=300,
        HttpMethod="PUT",
    )


def get_object_metadata(s3_key):
    return _client().head_object(Bucket=os.environ["S3_BUCKET_NAME"], Key=s3_key)


def create_download_url(s3_key, file_name):
    safe_name = file_name.replace('"', "'").replace("\r", "").replace("\n", "")
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": os.environ["S3_BUCKET_NAME"],
            "Key": s3_key,
            "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
        },
        ExpiresIn=300,
        HttpMethod="GET",
    )


def delete_object(s3_key):
    _client().delete_object(Bucket=os.environ["S3_BUCKET_NAME"], Key=s3_key)
