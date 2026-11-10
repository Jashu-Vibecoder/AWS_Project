# Database documentation

## Schema

Database: `cloudbox_db`. Table: `files` (InnoDB, utf8mb4 / utf8mb4_unicode_ci).

| Column | Type | Constraints / purpose |
|---|---|---|
| `id` | `INT UNSIGNED` | Primary key, auto increment |
| `file_name` | `VARCHAR(255)` | Original display/download filename after removing client path components and control characters |
| `s3_key` | `VARCHAR(500)` | Unique opaque S3 object key; never accepted as arbitrary download input |
| `file_size` | `BIGINT UNSIGNED` | Size in bytes |
| `file_type` | `VARCHAR(100)` | Validated MIME type |
| `status` | `VARCHAR(30)` | Defaults to `active` |
| `uploaded_at` | `TIMESTAMP` | Defaults to current time; APIs serialize UTC |

Indexes: primary key `id`; unique `uq_files_s3_key`; `idx_files_file_name`; composite `idx_files_status_uploaded_at`. There are no foreign-key relationships in the current schema. Source of truth is `database/schema.sql`.

## Example queries

```sql
SELECT id, file_name, file_size, file_type, uploaded_at
FROM files WHERE status = 'active'
ORDER BY uploaded_at DESC, id DESC LIMIT 100 OFFSET 0;

SELECT COUNT(*) AS total_files, COALESCE(SUM(file_size), 0) AS total_bytes
FROM files WHERE status = 'active';
```

Application queries bind values as parameters. The only interpolated SQL parts are fixed column lists/clauses and validated numeric pagination. Local fixture rows in `sample_data.sql` use non-real keys; do not run them in a deployed database.

## Connection and credentials

Flask and Lambda use PyMySQL with short connection/read/write timeouts and close each connection after a request. Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`; use `DB_PASSWORD` only for local development. AWS deployment should use `DB_SECRET_ARN` with a Secrets Manager JSON value containing `password`, and a separate least-privilege MySQL application account (not the RDS master). The app needs network reachability to private RDS port 3306. Lambda connection reuse is deliberately limited to one short-lived connection per invocation; size RDS and reserved Lambda concurrency to avoid exhausting connections.

## No schema changes

The implementation uses the existing columns and constraints. Duplicate upload confirmations rely on the unique S3 key and MySQL `ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)` behavior. No schema migration was added.

For the dedicated AWS foundation deployment, the SAM stack's private database bootstrap Lambda creates this same table definition and a `cloudbox_app` account with only `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on `cloudbox_db.files`. It reads the generated master/app credentials through scoped IAM permissions, performs TLS-verified MySQL connections, and does not log or return secret values. Keep its DDL in sync with `database/schema.sql` when making a schema change.
