# Screenshot evidence checklist

No screenshots have been captured or fabricated. Capture each item only after the corresponding real workflow or AWS resource has been verified. Store files in this directory with the suggested names and reference them in `../testing_report.md`.

## Application

- [ ] `01-dashboard.png` — CloudBox dashboard with live RDS totals.
- [ ] `02-file-selection.png` — selected file ready to upload.
- [ ] `03-upload-progress.png` — live S3 upload progress.
- [ ] `04-uploaded-file.png` — uploaded file visible in the library.
- [ ] `05-search-results.png` — filename search results from Flask/RDS.
- [ ] `06-download-complete.png` — downloaded file and original filename.
- [ ] `07-delete-confirmation.png` — delete confirmation dialog.
- [ ] `08-delete-verified.png` — file absent from list after S3 and DB cleanup.
- [ ] `09-mobile-layout.png` — responsive layout on a narrow viewport.

## AWS deployment

- [ ] `10-s3-buckets.png` — separate private frontend and file buckets with Block Public Access.
- [ ] `11-lambda-functions.png` — four file-operation Lambdas and database bootstrap function.
- [ ] `12-api-gateway-routes.png` — HTTP API routes and integrations.
- [ ] `13-ec2-instance.png` — CloudBox Flask EC2 instance and restricted security group.
- [ ] `14-rds-database.png` — private encrypted MySQL database and subnet group.
- [ ] `15-cloudfront-distribution.png` — CloudBox distribution, OAC, and API behaviors.
- [ ] `16-deployed-website.png` — working CloudFront site with live API response.

Never capture browser developer tools or console output that includes bearer tokens, secret values, signed S3 URLs, or credentials.
