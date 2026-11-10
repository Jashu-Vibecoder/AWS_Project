param(
    [Parameter(Mandatory = $true)][string]$InstanceId,
    [Parameter(Mandatory = $true)][string]$ArtifactBucketName,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$Region = 'ap-southeast-2'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BundlePath = Join-Path $PSScriptRoot 'out\cloudbox-backend.zip'
if ($InstanceId -notmatch '^i-[0-9a-f]{8,17}$') { throw 'InstanceId format is invalid.' }
if ($ArtifactBucketName -notmatch '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$') { throw 'ArtifactBucketName is invalid.' }
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 was not found in PATH.' }

$account = (& aws sts get-caller-identity --region $Region --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0) { throw 'AWS caller identity check failed.' }
$online = (& aws ssm describe-instance-information --filters "Key=InstanceIds,Values=$InstanceId" --region $Region --query 'InstanceInformationList[0].PingStatus' --output text).Trim()
if ($LASTEXITCODE -ne 0 -or $online -ne 'Online') { throw 'The target EC2 instance is not registered and Online in Systems Manager.' }
& aws s3api head-bucket --bucket $ArtifactBucketName --region $Region
if ($LASTEXITCODE -ne 0) { throw 'The artifact bucket is not accessible in the target account.' }
Write-Host "AWS account $account; region $Region; SSM instance $InstanceId; artifact bucket $ArtifactBucketName"
Write-Host 'This operation uploads a backend package and runs it on EC2 through Systems Manager. It updates the instance but does not alter infrastructure.'
if (-not $Apply) { Write-Host 'Preflight only. Rerun with -Apply to upload and deploy the backend.'; return }

$outDirectory = Join-Path $PSScriptRoot 'out'
New-Item -ItemType Directory -Force -Path $outDirectory | Out-Null
if (Test-Path -LiteralPath $BundlePath) { Remove-Item -LiteralPath $BundlePath -Force }
Compress-Archive -Path (Join-Path $ProjectRoot 'backend'), (Join-Path $ProjectRoot 'database') -DestinationPath $BundlePath -CompressionLevel Optimal
$release = [DateTime]::UtcNow.ToString('yyyyMMddHHmmss')
$objectKey = "deploy/releases/cloudbox-backend-$release.zip"
& aws s3 cp $BundlePath "s3://$ArtifactBucketName/$objectKey" --region $Region --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Backend artifact upload failed.' }

$commands = @(
    'set -euo pipefail',
    "release='$release'",
    "artifact_bucket='$ArtifactBucketName'",
    "artifact_key='$objectKey'",
    'release_dir="/opt/cloudbox/releases/$release"',
    'sudo install -d -o cloudbox -g cloudbox "$release_dir"',
    'aws s3 cp "s3://$artifact_bucket/$artifact_key" /tmp/cloudbox-backend.zip --only-show-errors',
    'sudo -u cloudbox unzip -oq /tmp/cloudbox-backend.zip -d "$release_dir"',
    'sudo -u cloudbox python3.12 -m venv /opt/cloudbox/venv',
    'sudo -u cloudbox /opt/cloudbox/venv/bin/pip install --disable-pip-version-check -r "$release_dir/backend/requirements.txt"',
    'sudo chown -R cloudbox:cloudbox "$release_dir"',
    'sudo ln -sfn "$release_dir" /opt/cloudbox/current',
    'sudo systemctl daemon-reload',
    'sudo systemctl enable --now cloudbox-flask',
    'sudo systemctl --no-pager --full status cloudbox-flask'
)
$parameters = @{ commands = $commands } | ConvertTo-Json -Compress
$commandId = (& aws ssm send-command --instance-ids $InstanceId --document-name AWS-RunShellScript --parameters $parameters --region $Region --query 'Command.CommandId' --output text).Trim()
if ($LASTEXITCODE -ne 0 -or -not $commandId) { throw 'Systems Manager did not accept the deployment command. The uploaded artifact can be safely retried.' }
& aws ssm wait command-executed --command-id $commandId --instance-id $InstanceId --region $Region
if ($LASTEXITCODE -ne 0) { throw "Systems Manager deployment failed. Command ID: $commandId. Inspect its invocation output before retrying." }
$invocation = & aws ssm get-command-invocation --command-id $commandId --instance-id $InstanceId --region $Region --output json | ConvertFrom-Json
if ($invocation.Status -ne 'Success') { throw "Backend deployment status: $($invocation.Status). Command ID: $commandId. Review CloudWatch/systemd logs." }
Write-Host $invocation.StandardOutputContent
Write-Host "Backend deployment succeeded. Verify https://<CloudFront-domain>/health. Command ID: $commandId"
