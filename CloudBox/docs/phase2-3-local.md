# CloudBox Phases 2 and 3: Local database and Flask API

These phases prepare a MySQL-compatible schema and a local Flask API. They do
not create AWS resources. Keep the database private and do not put passwords in
Git.

## Phase 2: Database

`database/schema.sql` creates `cloudbox_db.files`, including a unique S3 key
and indexes for filename and active-file upload ordering. `sample_data.sql`
contains local-only example metadata; its S3 keys do not identify real objects.

`backend/services/metadata_service.py` provides parameterized insert, lookup,
update, and metadata-delete operations. Repeating an insert with the same S3
key returns the existing row id without replacing its metadata. The caller
must verify the S3 object before inserting confirmed-upload metadata. Deleting
metadata does not delete an S3 object; the later file-operation workflow must
coordinate both operations.

## Phase 3: Flask API

Run `backend/app.py` with `python -m backend.app`. The app connects to MySQL
using values loaded from the project `.env` file or process environment.

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Checks the API and MySQL connection; returns 503 if MySQL is unavailable. |
| `GET /api/dashboard` | Returns file count, storage total, format counts, and recent uploads. |
| `GET /api/files` | Lists active metadata; accepts `q`, `limit` (1–100), and `offset` (0–100000). |
| `GET /api/files/search?q=...` | Search alias for the file-list endpoint. |

The read APIs omit internal S3 keys. CORS permits only origins in
`CORS_ALLOWED_ORIGINS`, defaulting to local development servers on port 5500.
Set that variable to the exact frontend origin when using another local port.
The backend binds to `127.0.0.1` when run directly. API routes can require the
single-user bearer token using `API_AUTH_REQUIRED` and a configured token or
Secrets Manager value. This demo gate is not a multi-user identity system.

## Local setup (PowerShell)

Run from the `CloudBox` directory:

```powershell
py -3.12 -m venv .venv
\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with the values for your local MySQL server. Use the MySQL client
to run `database/schema.sql`; for example, from a MySQL prompt:

```sql
SOURCE E:/AWS_Project/CloudBox/database/schema.sql;
```

For local fixtures only, run `database/sample_data.sql` from the MySQL prompt.
Do not load those fixture rows into a deployed database.

Start the backend:

```powershell
\.venv\Scripts\python.exe -m backend.app
```

In a second PowerShell window, run:

```powershell
curl.exe -i http://127.0.0.1:5000/health
curl.exe -i http://127.0.0.1:5000/api/dashboard
curl.exe -i http://127.0.0.1:5000/api/files
curl.exe -i "http://127.0.0.1:5000/api/files/search?q=report&limit=10&offset=0"
```

Expected successful responses use HTTP 200 and JSON with `success: true`.
`/health` reports database connectivity. With MySQL stopped or misconfigured,
it should return HTTP 503 without revealing credentials.

## Automated checks

From the `CloudBox` directory:

```powershell
\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The automated tests use a fake database connection to check SQL parameterization,
metadata CRUD behavior, API response validation, error handling, and CORS. They
do not replace running the schema and endpoints against a real local MySQL server.
