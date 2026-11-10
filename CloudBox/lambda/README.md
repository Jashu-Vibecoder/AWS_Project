# CloudBox Phase 4: S3 and Lambda code

This folder contains local Lambda handler code only. No AWS bucket, Lambda,
IAM role, RDS rule, or API route is created by these files or the unit tests.

## Handlers

| Handler | API Gateway contract (Phase 5) | Work |
| --- | --- | --- |
| `upload_url.handler` | `POST /upload-url` with `file_name`, `file_type`, and `file_size` | Validates the extension/type/25 MiB limit and signs a five-minute S3 PUT for an exact content type and length. |
| `confirm_upload.handler` | `POST /upload-confirm` with the returned `s3_key` | HEAD-checks the object and its size/type before idempotently inserting metadata. Invalid objects are removed. |
| `download_url.handler` | `GET /download-url/{id}` | Looks up an active record and returns a five-minute attachment URL. |
| `delete_file.handler` | `DELETE /files/{id}` | Deletes the object first, then its metadata; retrying the S3 delete is safe if metadata cleanup needs a retry. |
| `db_bootstrap.handler` | Private CloudFormation custom resource | Creates the existing `cloudbox_db.files` schema and a narrowly privileged `cloudbox_app` SQL user from Secrets Manager. It retains database contents when the application stack is removed. |

## Lambda runtime configuration

Set `S3_BUCKET_NAME` to the private object bucket name. Set `DB_HOST`,
`DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` for the private MySQL
database. For RDS TLS, set `DB_SSL_CA` to the deployed CA bundle path. The
functions use the Lambda execution role credential chain; never set AWS access
keys in the function environment or source.

The Lambda role needs narrowly scoped S3 `PutObject`, `GetObject`, and
`DeleteObject` permissions for the configured bucket/prefix, plus network access
to RDS and the minimum required RDS permissions. RDS security groups must accept
the database port only from the Lambda security group. API Gateway must not
expose these handlers publicly until an access restriction is chosen and
configured. API Gateway CORS is Phase 5; S3 PUT CORS for the frontend must also
be configured before browser uploads can work.

The database bootstrap function is private to the CloudFormation stack and has
its own role with access to only the RDS master and app credential secrets. It
does not log or return secret values. Its SQL matches `database/schema.sql`;
keep the two definitions synchronized if the schema changes.

Presigned URLs expire after five minutes. The PUT signature binds content type
and declared content length; upload confirmation independently checks actual
object metadata and removes an object that exceeds the limit. S3 bucket
encryption, public-access blocking, lifecycle rules, and bucket CORS remain
infrastructure configuration tasks and are not verified by local unit tests.

## Local test

From the `CloudBox` project directory:

```powershell
\.venv\Scripts\python.exe -m pip install -r lambda\requirements.txt
\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The Lambda tests stub S3 and MySQL interactions. They do not call AWS or prove
that deployed IAM, bucket policies, RDS networking, and API Gateway routes work.
