# Deployment guide (prepared, not executed)

Target region is fixed to `ap-southeast-2`. `foundation.yaml` provisions the CloudBox VPC, private RDS MySQL, EC2 Flask host, internal NLB, endpoint access, artifact bucket, and app secrets. `template.yaml` provisions private frontend/file buckets, CloudFront OAC, same-origin routes, an HTTP API with a private VPC Link integration to Flask, and four Lambda functions. These stacks create a separate CloudBox environment; the current account has SecureWatch-named resources that were not adopted or changed. The PowerShell scripts require `-Apply` before writes. The current IAM user has EC2, RDS, and S3 full-access policies attached, but policy simulation still denies required CloudFormation/service actions and does not allow IAM role creation or CloudFront distribution creation. The Organizations API denied inspection of the controlling policy, so deployment has not been run.

## Before deployment

1. Confirm AWS principal, region, current resources, account-specific pricing, and promotional eligibility. The existing `securewatch-*` bucket, EC2, RDS, Lambda, API, and CloudFront distribution appear to belong to another app; do not point the CloudBox deployment scripts at them or replace them without confirming ownership.
2. Create the dedicated foundation stack. It uses two public subnets and two private subnets, no NAT Gateway, an S3 gateway endpoint, and a Secrets Manager interface endpoint. RDS port 3306 accepts only the EC2 and Lambda security groups. EC2 has no public inbound rule; the internal NLB accepts HTTP only from the API Gateway VPC Link security group and forwards to EC2. All three S3 buckets block public access, encrypt data at rest, and deny non-TLS requests. The interface endpoint, public EC2 IPv4 address, internal NLB, and VPC Link can incur ongoing charges.
3. Deploy the SAM application stack with the foundation outputs. Its private, one-purpose database bootstrap Lambda creates the `cloudbox_db.files` schema and a least-privilege `cloudbox_app` user from Secrets Manager; it never returns or logs secret values. The custom resource is idempotent and retains database content if the app stack is removed. The deployment script then updates the app stack with the generated CloudFront origin so the file bucket CORS allowlist contains that exact hostname, not a wildcard. The stack outputs include all four file-operation Lambda physical names and the database bootstrap Lambda name.
4. Deploy the Flask package to EC2 through Systems Manager, then publish frontend files with both API base URLs set to the CloudFront URL and `-AuthRequired`. Retrieve the generated sign-in token directly in Secrets Manager and enter it in the login page. Invalidate CloudFront after publishing.
5. Price check from the AWS Price List API on 2026-11-10: at 730 hours/month, the planned Sydney Linux shared `t3.micro` EC2, Single-AZ MySQL `db.t3.micro` RDS, its default 20 GiB GP3 storage, the internal NLB hourly charge, and a Secrets Manager interface endpoint in two AZs total about $68.76 USD/month. This known baseline excludes EC2 EBS, RDS backups, NLB capacity units, public IPv4, API Gateway VPC Link, S3, CloudFront, API Gateway requests, Lambda, data transfer, tax, and account-specific credits or promotional eligibility. Recheck current prices and eligibility in the AWS Pricing Calculator before provisioning. Stopping EC2/RDS does not remove storage, snapshot, endpoint, secret, load balancer, or public IPv4 costs.

## Scripts

All commands are run in PowerShell from `E:\AWS_Project\CloudBox`.

- `deploy_frontend.ps1`: checks tools/identity/region, writes deployment URLs into `frontend/js/config.js`, and syncs static assets to an existing bucket without deleting remote files. Use `-Apply` only after reviewing the target and config.
- `deploy_lambda.ps1`: optional standalone helper that packages and updates four explicitly named existing Lambda function code packages. The CloudBox deployment uses SAM instead; do not use this helper for stack-managed CloudBox functions because it would create CloudFormation drift. Requires `-Apply`.
- `deploy_foundation.ps1`: read-only identity/stack preflight, then creates the dedicated foundation stack only with `-Apply`; it refuses to update an existing stack.
- `deploy_cloudbox.ps1`: validates/builds the SAM app stack from foundation outputs; deploys only with `-Apply`.
- `deploy_backend.ps1`: packages backend and schema, uploads to the private artifact bucket, and deploys/restarts the production Gunicorn service through SSM when `-Apply` is present.
- `deploy_cloudfront.ps1`: creates an invalidation for an existing distribution; this changes cache state and requires `-Apply`.

The foundation and SAM stacks are split so the dependency order is explicit. Each file-operation Lambda receives its own execution role with only the S3 actions and Secrets Manager secrets that handler needs. A separate private CloudFormation custom resource role initializes the database schema and least-privilege SQL user through the VPC-attached bootstrap Lambda; secret values stay in Secrets Manager and never enter source, command output, or chat.

### SAM preflight and deployment

From `E:\AWS_Project\CloudBox`:

```powershell
sam validate --lint --template-file deployment\template.yaml
sam build --template-file deployment\template.yaml
```

`deploy_foundation.ps1` and `deploy_cloudbox.ps1` print their targets and costs before the `-Apply` gate. The current principal cannot execute the create operations. A successful `sam validate` does not deploy anything; `sam deploy` changes AWS resources.

If the account permissions are later updated, run these in PowerShell from `E:\AWS_Project\CloudBox`, using the stack outputs for the placeholder values:

```powershell
.\deployment\deploy_foundation.ps1 -Apply
.\deployment\deploy_cloudbox.ps1 -Apply
.\deployment\deploy_backend.ps1 -InstanceId <BackendInstanceId> -ArtifactBucketName <FileArtifactsBucketName> -Apply
$site = '<CloudFrontUrl>'
.\deployment\deploy_frontend.ps1 -BucketName <FrontendBucketName> -FlaskApiBaseUrl $site -FileApiBaseUrl $site -AuthRequired -Apply
.\deployment\deploy_cloudfront.ps1 -DistributionId <CloudFrontDistributionId> -Apply
```

The placeholders are outputs from CloudFormation and must be checked against the new `cloudbox-*` stacks. Do not use SecureWatch resource IDs or buckets here.

## Verification

After deployment, check `/health`, `/api/dashboard`, `/api/files`, all four API Gateway routes, CloudFront HTTPS, browser CORS, and a disposable file's metadata/object across upload, download, and delete. Record real output and screenshots in `../docs/testing_report.md` only after verifying it.

## Cleanup

Delete the application stack (`cloudbox-app`) before the foundation stack (`cloudbox-foundation`) so API Gateway/Lambda/CloudFront resources are removed before their network and database dependencies. All three S3 buckets and the RDS database are retained by their stack deletion policies. First back up any data to keep, delete both stacks, then empty and manually delete the retained frontend, file, and artifact buckets only after confirming their contents are disposable. The retained buckets continue to incur storage charges until removed. Deleting the foundation stack creates an RDS snapshot under its `DeletionPolicy`; that snapshot remains billable until separately deleted. Review CloudFront distribution status and every stack event; deleting compute can also leave EBS volumes, backups, logs, secrets, interface endpoints, NLB/VPC Link, or public IPv4 resources billable. No destructive cleanup script is provided.
