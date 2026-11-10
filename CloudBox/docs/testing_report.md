# CloudBox testing report

Updated: 2026-11-10. Test evidence below is local unless explicitly labeled AWS. No screenshots or live service results have been fabricated.

| ID | Feature | Steps | Expected | Actual | Status / evidence |
|---|---|---|---|---|---|
| L-01 | Flask health | Flask test client with mocked MySQL success and failure | 200 with connected DB; 503 without internals on DB failure | Both response paths matched; no password detail returned | PASS — `tests/test_api.py` |
| L-02 | Dashboard, list, search | Mock route/service calls; exercise pagination, wildcard search, and a SQL injection-shaped search string | JSON stats, valid page values, and user input retained as a parameter | Expected payloads; injection-shaped text remained a parameter value | PASS — `tests/test_api.py`, `tests/test_backend.py` |
| L-03 | Flask/Lambda auth and CORS | Call Flask and all four Lambda handlers without tokens; call Flask with valid token; test configured and untrusted origins | Protected routes return 401 without token; valid token succeeds; CORS only for configured origin | Expected status and CORS behavior observed | PASS — `tests/test_api.py`, `tests/test_lambda.py` |
| L-04 | Upload URL Lambda | Submit valid, malformed, missing/blank-name, unsupported, MIME-mismatched, oversized requests; simulate S3 signing failure | Reject invalid requests; return short-lived URL for valid input; report S3 failure as 503 | Invalid requests rejected; UUID key returned; S3 failure returned 503 | PASS — mocked handler tests in `tests/test_lambda.py` |
| L-05 | Upload confirmation Lambda | Mock S3 HEAD and DB insert; repeat confirmation; simulate oversized/missing object and DB error | Verify object before metadata; deduplicate; clean invalid object; never write metadata for a missing object | Expected insert/idempotency/cleanup/error behaviors observed | PASS — mocked S3/DB tests in `tests/test_lambda.py` |
| L-06 | Download URL Lambda | Test active, missing, invalid-ID, and missing-S3-object cases | Sign only for an active DB row with an existing object | Expected 200/400/404 paths; signing skipped for missing records/objects | PASS — mocked handler tests in `tests/test_lambda.py` |
| L-07 | Delete Lambda | Mock row lookup, S3 delete, DB delete; simulate DB cleanup failure and retry | Delete object before row; retry completes cleanup safely | Order matched; first DB-failure attempt returned 503 and retry succeeded | PASS — mocked S3/DB tests in `tests/test_lambda.py` |
| L-08 | Database bootstrap | Mock master/app secret reads, DB DDL/grants, and CloudFormation response | Create schema/table and least-privilege grants; never return secrets; retain DB on delete | Expected SQL/response; delete performed no DB connection | PASS — local mocks in `tests/test_db_bootstrap.py` |
| L-09 | Frontend JavaScript | Run Node syntax parser on frontend modules | All modules parse | All checked files parsed successfully | PASS — local syntax check |
| L-10 | Deployment templates | Run CloudFormation `ValidateTemplate`, SAM `validate --lint`, `sam build`, and `cfn-lint` | Templates validate and five Lambda packages build | Current SAM `validate --lint` and `cfn-lint` runs pass for both templates. The sandbox denied SAM temporary-directory cleanup (`WinError 5`); the same build then succeeded with elevated local filesystem access and produced all five function packages. No deployment was performed | PASS — local template validation, lint, and package build |
| L-11 | Lambda IAM separation | Inspect SAM function policies and validate/build the application template | Each file-operation handler receives its own generated execution role with only its required S3 actions and Secrets Manager secret ARNs | Upload URL is limited to object writes and the auth secret; confirmation and download can read required secrets; object read/delete actions are limited to handlers that need them | PASS — source policy review plus SAM validation/build; live role policies remain unverified |
| L-12 | Deployed file-bucket CORS | Inspect bucket CORS and deployment update sequence | Only localhost development origins and the exact deployed CloudFront origin are allowed; no wildcard CloudFront origins | Template accepts a frontend-origin parameter, and the deployment script sets it after CloudFront creates its hostname; no `*.cloudfront.net` entry remains | PASS — static review and PowerShell parse; live browser CORS remains unverified |
| L-13 | Lambda name outputs | Inspect SAM outputs and run `sam validate --lint` / `cfn-lint` | Export names for all four file-operation functions and the database bootstrap function | Five outputs reference the matching SAM function logical IDs; physical names are available after deploy and printed by the deploy script | PASS — template lint/validation; no live stack outputs exist |
| L-14 | Filename preservation | Upload URL handler and download URL signing helper with Unicode, spaces, quotes, controls, and a client-supplied path | Store and download using the original display filename while preventing path disclosure and header injection | The handler removes client path components/control characters while retaining Unicode and spaces; the signed download response includes an ASCII fallback and percent-encoded UTF-8 filename parameter | PASS — local handler and S3-helper unit tests; no live S3 request |
| A-01 | MySQL connectivity | Call Flask health/dashboard through test client with no local MySQL | Real MySQL connection and usable endpoints | Local DB unavailable; API returned 503 `database_unavailable` | NOT VERIFIED — no configured/running local MySQL |
| A-02 | AWS identity and write permissions | Read STS identity, attached policies, inline policies, groups, CloudFormation stacks, and simulate required actions | Confirm deployment principal and available permissions | Rechecked this turn: attached policies remain `AmazonEC2FullAccess`, `AmazonRDSFullAccess`, `AmazonS3FullAccess`, `ReadOnlyAccess`; no inline/group policies or CloudBox stacks. Simulation again explicitly denies CloudFormation create/change-set/execute, required EC2/RDS/S3/Lambda/API Gateway/SSM operations; IAM role/pass-role and CloudFront creation are implicitly denied. Organizations inspection previously returned AccessDenied, so the SCP document remains unavailable | READ-ONLY VERIFIED — AWS MCP; no write call made |
| A-03 | S3/API/Lambda upload-download-delete | Upload a disposable file; verify S3 object and RDS row; download and delete | All operations succeed and object/row are removed | Not run; no CloudBox stack deployed | NOT RUN — AWS write permissions unavailable |
| A-04 | EC2/RDS/API Gateway/CloudFront | Deploy and call actual endpoints in `ap-southeast-2` | Services healthy and routes integrated | Not run; no CloudBox resources deployed | NOT RUN — AWS write permissions unavailable |
| A-05 | Responsive UI/screenshots | Request the local static dashboard and inspect desktop/mobile layouts | Local page serves without horizontal clipping; genuine screenshots at each viewport | Local `GET /` returned HTTP 200. A genuine desktop capture exposed horizontal overflow; `.main-content` width now subtracts the fixed sidebar width. Recapture failed because Chrome reported `CreateFile: Access is denied` and a Mojo platform-channel access error; the CUA browser host was also unavailable. No stale screenshot was retained | PARTIAL — CSS fix applied; responsive rendering and screenshots remain unverified |
| A-06 | Regional deployment prerequisites | Read RDS orderable options, EC2 instance offerings, and the public Amazon Linux SSM AMI parameter in `ap-southeast-2` | Planned EC2/RDS types and AMI lookup are available | `t3.micro` is offered in Sydney; the SSM AMI parameter exists; RDS returned 76 MySQL `db.t3.micro` VPC options, including GP3 options | READ-ONLY VERIFIED — AWS MCP; no resources created |

## Current AWS inventory (ap-southeast-2)

Read-only state rechecked 2026-11-10. These resources are named `securewatch-*`, not CloudBox, and were left untouched. They should not be adopted as CloudBox without confirming ownership and purpose.

| Service | Existing resource | State / notes |
|---|---|---|
| S3 | `securewatch-frontend-356252963459` | Existing frontend bucket, origin for the current distribution |
| EC2 | `securewatch-backend` (`i-0b70aa399a5400002`) | Running `t3.micro` in the default VPC; can continue incurring compute, disk, and public IPv4 charges |
| RDS | `securewatch-db` | Available MySQL 8.4, `db.t4g.micro`, 20 GiB, encrypted, single-AZ and not publicly accessible |
| Lambda | `securewatch-event-analysis` | Ruby 4.0; its configured role is named `PowerUserRole` and should be reviewed separately |
| API Gateway | `securewatch-event-analysis-API` (`ecmfa4oup8`) | Existing HTTP API |
| CloudFront | `EGCPMA0JRFW0N` (`d1ip1exrumesco.cloudfront.net`) | Deployed, OAC-protected origin is the SecureWatch bucket, `PriceClass_All`; its reported minimum viewer TLS setting is `TLSv1`, which merits owner review |
| Networking | Default VPC `vpc-086247a993f562680` | Three default public subnets were returned; no CloudBox private network was identified |

The existing CloudFront distribution and bucket are an unrelated named application and should not be overwritten. The prepared CloudBox templates create a separate CloudBox VPC/database/compute and delivery stack, which can add charges. Current CloudBox deployment is blocked by IAM/SCP permissions. An IAM `GetUser` response also contained secret-like values in user tags; values were suppressed and not written to project files. Review those tags and rotate/remove any exposed credentials through a trusted IAM admin process.

## Local command

From `E:\AWS_Project\CloudBox`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Most recent run: 47 tests passed. AWS and SQL are mocked by the tests; this is not end-to-end evidence. The system `python` command in this environment failed before test discovery because its Python runtime could not load the `encodings` module; the project virtualenv interpreter succeeded.

## Missing live tests

To complete the real-world test matrix, first obtain an AWS principal allowed by account and organization policy to create the dedicated CloudBox stacks. Deploy foundation and app stacks, publish Flask and the frontend, then upload a disposable supported file, verify its S3 object and RDS row, download it, delete it, and verify both are gone. The app stack initializes its own schema and DB user. Capture genuine screenshots only after those actions. Do not use `sample_data.sql` as live object metadata.

The requested screenshot list is in `docs/screenshots/README.md`; every item remains uncaptured until a live deployment exists.
