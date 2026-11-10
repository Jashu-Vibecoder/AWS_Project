# CloudBox

CloudBox is a single-user file library built with a vanilla JavaScript frontend, Flask metadata API, MySQL, S3, Lambda, and API Gateway. The browser sends file bytes directly to private S3 using short-lived presigned URLs; Flask reads dashboard/list metadata while Lambda handles upload confirmation, downloads, and deletes.

## Problem statement and objectives

Small teams need a simple way to store and manage files without exposing a storage bucket or maintaining a public database. CloudBox demonstrates a browser-based file library whose metadata is searchable in MySQL and whose file bytes stay in private S3. The project objectives are to deliver a responsive dashboard, upload/download/delete through short-lived signed links, keep metadata access parameterized and authenticated for the single-user demo, and document a repeatable AWS deployment with clear cost and cleanup guidance.

## Features

- Dashboard totals, recent uploads, format breakdown, filename search, and pagination.
- File selection and drag/drop with upload progress.
- Presigned S3 PUT/GET links and delete confirmation.
- Opaque S3 object keys, server-side validation, parameterized SQL, optional bearer-token gate, and no AWS keys in the browser.
- Responsive static frontend with local-development defaults.

## Technology and structure

| Area | Technology |
|---|---|
| Frontend | HTML, CSS, browser JavaScript |
| Metadata API | Python 3, Flask, Flask-Cors, PyMySQL |
| File operations | Python Lambda handlers, boto3 |
| Database | MySQL / Amazon RDS MySQL |
| Storage and delivery | Private S3, CloudFront OAC |
| HTTP endpoints | API Gateway HTTP API |

```text
backend/          Flask app, routes, MySQL services, optional auth
database/         schema.sql and local-only sample_data.sql
frontend/         static pages, styles, API client, UI modules
lambda/           four file-operation handlers, database bootstrap custom resource, and shared S3, DB, auth, validation helpers
deployment/       guarded deployment helpers and deployment notes
docs/             architecture, API, database, testing, audit notes
tests/            local unit tests; AWS services are mocked
```

## Local setup (PowerShell)

Run commands from `E:\AWS_Project\CloudBox`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Create a MySQL database and application user, then run `database\schema.sql` using your MySQL client. Set the local connection values in `.env`; do not commit that file. Do not run `database\sample_data.sql` against deployed data: its S3 keys are local fixtures and do not reference actual S3 objects.

Start Flask:

```powershell
$env:FLASK_DEBUG = "false"
.\.venv\Scripts\python.exe -m flask --app backend.app:create_app run --host 127.0.0.1 --port 5000
```

Serve `frontend\` from `http://localhost:5500` with your preferred local static server (for example VS Code Live Server). `frontend\js\config.js` defaults Flask to `http://127.0.0.1:5000` and leaves the file API unset until configured. Configure `CORS_ALLOWED_ORIGINS` to include the exact local frontend origin. The local dashboard and file listing require a reachable MySQL database; there is no fake-data fallback.

## Configuration

See `.env.example`. Local deployments can use `DB_PASSWORD`; AWS deployments should set `DB_SECRET_ARN` and grant the instance role `secretsmanager:GetSecretValue` only for that secret. Optional API token auth uses `API_AUTH_REQUIRED=true` and `AUTH_TOKEN_SECRET_ARN` (JSON secret with a `token` field), or a local `CLOUDBOX_API_TOKEN`. Never put an access token in frontend config or source control. The frontend keeps a manually entered token in session storage only.

Lambda environment variables: `S3_BUCKET_NAME`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_SECRET_ARN` or local `DB_PASSWORD`, `DB_CONNECT_TIMEOUT`, optional `DB_SSL_CA`, `API_AUTH_REQUIRED`, `AUTH_TOKEN_SECRET_ARN`, and `AWS_REGION`. Lambda uses its execution role for AWS access.

## Database

The schema is `cloudbox_db.files`; `database/schema.sql` is authoritative. See [database documentation](docs/database.md). Each row stores the original filename and metadata; the unique `s3_key` points to an opaque generated key. Create a narrowly privileged application DB user for deployment instead of using the RDS master user.

## API overview

Flask: `GET /health`, `GET /api/dashboard`, `GET /api/files`, and `GET /api/files/search?q=...`.

API Gateway: `POST /upload-url`, `POST /upload-confirm`, `GET /download-url/{id}`, `DELETE /files/{id}`. Full request and response formats are in [API documentation](docs/api_documentation.md).

## AWS deployment status

Target region: `ap-southeast-2` (Sydney). `deployment/foundation.yaml` defines the dedicated VPC, EC2, RDS, and secret foundation. `deployment/template.yaml` defines private S3 buckets, CloudFront OAC and API routing, API Gateway, and Lambda. See `deployment/README.md` for the deployment order and database bootstrap. The existing SecureWatch resources in the account were left untouched.

**This checkout has not been deployed or verified against live AWS resources.** A current AWS MCP read-only audit found attached `AmazonEC2FullAccess`, `AmazonRDSFullAccess`, `AmazonS3FullAccess`, and `ReadOnlyAccess` policies, but effective-policy simulation still explicitly denies CloudFormation stack operations, key EC2/RDS/S3/Lambda/API Gateway/Secrets Manager/SSM operations; IAM role creation and pass-role plus CloudFront distribution creation are implicitly denied. The Organizations API denied access to the SCP document, so the controlling deny policy could not be identified by name. No CloudBox stacks exist and no provisioning command was run. Local unit tests do not prove a live upload/download/delete workflow. Live verification requires an authorized AWS principal and organization policy that permits the planned resources.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests mock AWS and database calls; they verify handler behavior and API contracts locally. See [testing report](docs/testing_report.md) for coverage and live-test blockers.

## Costs and cleanup

Potential charges include EC2 uptime and EBS, RDS instance/storage/backups, S3 storage and requests, CloudFront data transfer/requests, API Gateway requests, Lambda duration, Secrets Manager secret storage, a Secrets Manager interface endpoint, the internal NLB and API Gateway VPC Link, and public IPv4. On 2026-11-10, the AWS Price List API returned Sydney public on-demand rates of $0.0132/hour for the planned Linux shared `t3.micro` EC2 and $0.026/hour for the planned Single-AZ MySQL `db.t3.micro` RDS instance; 20 GiB GP3 MySQL storage at $0.138/GB-month; $0.0252 per NLB-hour; and $0.013 per hour for each Secrets Manager interface endpoint AZ. At 730 hours/month and two endpoint AZs, these known baseline charges total about $68.76 USD/month (EC2 and RDS instance-hours, default RDS storage, NLB hourly charge, and endpoint hourly charge). This excludes EC2 EBS, RDS backups, NLB capacity units, public IPv4, API Gateway VPC Link, S3, CloudFront, data transfer, requests, Lambda, secret storage, tax, and account credits or promotional eligibility. This is a public on-demand estimate, not an account-specific quote; request volume and data use can change it. Stopping EC2 does not remove EBS or public IPv4 costs; stopping RDS does not remove storage/backup costs. Avoid NAT Gateway for the initial demo, but private-subnet egress and service endpoints must be designed explicitly. Recheck live prices and account eligibility in the [AWS Pricing Calculator](https://calculator.aws/) before provisioning. Cleanup should be done through the owning stack after backing up required data. The deployment retains its S3 buckets and RDS snapshot when the stacks are deleted; manually remove retained buckets and snapshots only after confirming their contents are disposable, since they continue to incur storage charges.

## Known limitations

- Single-user bearer token is a demo gate, not multi-user identity management. Use Cognito or another proper identity provider before real users.
- There is no end-to-end AWS evidence because deployment is blocked by account permissions and database/network configuration.
- The local Flask development server is for local development only; use a production WSGI server behind a correctly configured reverse proxy in deployment.
- Cross-service delete cannot be atomic. S3 deletion is idempotent, so repeating a delete request can complete DB cleanup after a partial failure; operators should reconcile any remaining metadata rows.
