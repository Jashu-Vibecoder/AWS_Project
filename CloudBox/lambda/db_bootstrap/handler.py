"""Initialize the CloudBox schema and least-privilege DB account once per stack."""

import json
import logging
import os
import time
from urllib.request import Request, urlopen

import boto3
import certifi
import pymysql


logger = logging.getLogger()
logger.setLevel(logging.INFO)
_SECRETS_CLIENT = None
PHYSICAL_RESOURCE_ID = "cloudbox-database-bootstrap"


def _secret(secret_arn):
    global _SECRETS_CLIENT
    if _SECRETS_CLIENT is None:
        _SECRETS_CLIENT = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION"))
    raw = _SECRETS_CLIENT.get_secret_value(SecretId=secret_arn)["SecretString"]
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON secret")
    return value


def _connect(host, username, password):
    return pymysql.connect(
        host=host,
        port=3306,
        user=username,
        password=password,
        database="mysql",
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
        autocommit=True,
        ssl={"ca": certifi.where(), "check_hostname": True},
    )


def _initialize_database(properties):
    master = _secret(properties["DatabaseMasterSecretArn"])
    app = _secret(properties["DatabaseAppSecretArn"])
    username = app.get("username")
    password = app.get("password")
    if username != "cloudbox_app" or not isinstance(password, str) or not password:
        raise ValueError("Database application secret has an unexpected shape")

    last_error = None
    connection = None
    for attempt in range(12):
        try:
            connection = _connect(properties["DatabaseHost"], master["username"], master["password"])
            break
        except pymysql.MySQLError as exc:
            last_error = exc
            if attempt < 11:
                time.sleep(5)
    if connection is None:
        raise RuntimeError("Database did not become reachable") from last_error

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS cloudbox_db "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS cloudbox_db.files ("
                "id INT UNSIGNED NOT NULL AUTO_INCREMENT,"
                "file_name VARCHAR(255) NOT NULL,"
                "s3_key VARCHAR(500) NOT NULL,"
                "file_size BIGINT UNSIGNED NOT NULL,"
                "file_type VARCHAR(100) NULL,"
                "status VARCHAR(30) NOT NULL DEFAULT 'active',"
                "uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                "PRIMARY KEY (id),"
                "UNIQUE KEY uq_files_s3_key (s3_key),"
                "KEY idx_files_file_name (file_name),"
                "KEY idx_files_status_uploaded_at (status, uploaded_at)"
                ") ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                "CREATE USER IF NOT EXISTS 'cloudbox_app'@'%' IDENTIFIED BY %s",
                (password,),
            )
            cursor.execute(
                "ALTER USER 'cloudbox_app'@'%' IDENTIFIED BY %s",
                (password,),
            )
            cursor.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON cloudbox_db.files "
                "TO 'cloudbox_app'@'%'"
            )
    finally:
        connection.close()


def _send_response(event, context, status, reason):
    response = {
        "Status": status,
        "Reason": reason,
        "PhysicalResourceId": event.get("PhysicalResourceId", PHYSICAL_RESOURCE_ID),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "NoEcho": True,
        "Data": {"Database": "cloudbox_db"},
    }
    body = json.dumps(response).encode("utf-8")
    request = Request(
        event["ResponseURL"],
        data=body,
        method="PUT",
        headers={"content-type": "", "content-length": str(len(body))},
    )
    with urlopen(request, timeout=10) as reply:
        logger.info("CloudFormation database bootstrap response sent: HTTP %s", reply.status)


def handler(event, context):
    request_type = event.get("RequestType")
    status = "SUCCESS"
    reason = "Database bootstrap completed"
    try:
        if request_type in {"Create", "Update"}:
            _initialize_database(event["ResourceProperties"])
        elif request_type != "Delete":
            raise ValueError("Unsupported CloudFormation request type")
        else:
            # Keep the database and app account if the application stack is removed.
            reason = "Database data retained"
    except Exception:
        logger.exception("CloudBox database bootstrap failed")
        status = "FAILED"
        reason = "Database bootstrap failed; inspect this function's logs"
    _send_response(event, context, status, reason)
