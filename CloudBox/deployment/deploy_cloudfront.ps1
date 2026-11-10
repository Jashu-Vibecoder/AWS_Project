param(
    [Parameter(Mandatory = $true)][string]$DistributionId,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$Region = 'ap-southeast-2'
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 was not found in PATH.' }
if ($DistributionId -notmatch '^E[A-Z0-9]{10,}$') { throw 'DistributionId format is invalid.' }
$account = (& aws sts get-caller-identity --region $Region --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0) { throw 'AWS caller identity check failed.' }
Write-Host "AWS account $account; target distribution $DistributionId"
Write-Host 'This operation requests a CloudFront cache invalidation and may incur charges beyond the included allowance.'
if (-not $Apply) { Write-Host 'Preflight only. Rerun with -Apply to invalidate /*.'; return }
$result = & aws cloudfront create-invalidation --distribution-id $DistributionId --paths '/*' --region $Region --output json --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw 'CloudFront invalidation request failed.' }
Write-Host $result
