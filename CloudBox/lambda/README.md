# CloudBox Phase 4: S3 and Lambda code

This folder contains local Lambda handler code only. No AWS bucket, Lambda,
IAM role, RDS rule, or API route is created by these files or the unit tests.

## Handlers

| SAM logical ID / name output | Handler | API Gateway contract | Work |
| --- | --- | --- | --- |
| `UploadUrlFunction` / `UploadUrlFunctionName` | `upload_url.handler` | `POST /upload-url` with `file_name`, `file_type`, and `file_size` | Removes client path components and control characters while preserving the display filename; validates extension/type/25 MiB limit and signs a five-minute S3 PUT for an exact content type and length. |
| `ConfirmUploadFunction` / `ConfirmUploadFunctionName` | `confirm_upload.handler` | `POST /upload-confirm` with the returned `s3_key` | HEAD-checks the object and its size/type before idempotently inserting metadata. Invalid objects are removed. |
| `DownloadUrlFunction` / `DownloadUrlFunctionName` | `download_url.handler` | `GET /download-url/{id}` | Looks up an active record and returns a five-minute attachment URL. |
| `DeleteFileFunction` / `DeleteFileFunctionName` | `delete_file.handler` | `DELETE /files/{id}` | Deletes the object first, then its metadata; retrying the S3 delete is safe if metadata cleanup needs a retry. |
| `DatabaseBootstrapFunction` / `DatabaseBootstrapFunctionName` | `db_bootstrap.handler` | Private CloudFormation custom resource | Creates the existing `cloudbox_db.files` schema and a narrowly privileged `cloudbox_app` SQL user from Secrets Manager. It retains database contents when the application stack is removed. |

The SAM template exports each generated physical function name as a stack output. The outputs are unavailable until the stack is deployed; the logical IDs above are stable in the source template.

## Lambda runtime configuration

Set `S3_BUCKET_NAME` to the private object bucket name. Set `DB_HOST`,
`DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` for the private MySQL
database. For RDS TLS, set `DB_SSL_CA` to the deployed CA bundle path. The
functions use the Lambda execution role credential chain; never set AWS access
keys in the function environment or source.

Each file-operation Lambda has a separate execution role. Upload URL can write
only under `uploads/` and read only the auth token secret; confirmation can read
and remove objects and read the DB/auth secrets; download can read objects and
the DB/auth secrets; delete can read/remove objects and read the DB/auth
secrets. These functions need VPC network access to MySQL over TCP 3306, not
RDS control-plane IAM permissions. The RDS security group accepts that port
only from application security groups.

The API Gateway routes are public HTTPS endpoints guarded by the configured
single-user bearer token in each Lambda handler; they do not use an API Gateway
authorizer. Use a proper identity provider before supporting multiple users.
The template allows the local development origins in API Gateway CORS. The S3
bucket CORS allows local origins plus the exact CloudFront origin, which the
deployment helper sets after distribution creation.

The database bootstrap function is private to the CloudFormation stack and has
its own role with access to only the RDS master and app credential secrets. It
does not log or return secret values. Its SQL matches `database/schema.sql`;
keep the two definitions synchronized if the schema changes.

Presigned URLs expire after five minutes. The PUT signature binds content type
and declared content length; upload confirmation independently checks actual
object metadata and removes an object that exceeds the limit. The CloudFormation
template defines S3 encryption, Block Public Access, lifecycle rules, and CORS;
local unit tests do not verify those live settings.

## Local test

From the `CloudBox` project directory:

```powershell
\.venv\Scripts\python.exe -m pip install -r lambda\requirements.txt
\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The Lambda tests stub S3 and MySQL interactions. They do not call AWS or prove
that deployed IAM, bucket policies, RDS networking, and API Gateway routes work.
