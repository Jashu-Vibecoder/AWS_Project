"""Lazy Secrets Manager access shared by Lambda helpers."""

import json

_CACHE = {}
_CLIENT = None


def get_secret(secret_arn):
    global _CLIENT
    if secret_arn not in _CACHE:
        import boto3

        if _CLIENT is None:
            _CLIENT = boto3.client("secretsmanager")
        response = _CLIENT.get_secret_value(SecretId=secret_arn)
        raw_value = response["SecretString"]
        try:
            _CACHE[secret_arn] = json.loads(raw_value)
        except (TypeError, ValueError):
            _CACHE[secret_arn] = raw_value
    return _CACHE[secret_arn]
