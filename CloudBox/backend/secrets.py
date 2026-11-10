"""Load Secrets Manager values lazily without logging secret contents."""

import json

_CACHE = {}


def get_secret(secret_arn, region=None):
    if secret_arn not in _CACHE:
        import boto3

        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_arn)
        raw_value = response["SecretString"]
        try:
            _CACHE[secret_arn] = json.loads(raw_value)
        except (TypeError, ValueError):
            _CACHE[secret_arn] = raw_value
    return _CACHE[secret_arn]
