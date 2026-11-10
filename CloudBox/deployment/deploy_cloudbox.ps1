param(
    [string]$StackName = 'cloudbox-app',
    [string]$DatabaseBootstrapRevision = '1',
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$Region = 'ap-southeast-2'
$FoundationStack = 'cloudbox-foundation'
$Template = Join-Path $PSScriptRoot 'template.yaml'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 was not found in PATH.' }
$SamCommand = Get-Command sam -ErrorAction SilentlyContinue
$Sam = if ($SamCommand) { $SamCommand.Source } else { $null }
if (-not $Sam) {
    $SamCandidates = @(
        (Join-Path $ProjectRoot '.venv\Scripts\sam.exe'),
        (Join-Path (Split-Path $ProjectRoot -Parent) '.venv\Scripts\sam.exe')
    )
    foreach ($candidate in $SamCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $Sam = $candidate; break }
    }
}
if (-not $Sam) { throw 'AWS SAM CLI was not found in PATH or either project virtual environment.' }
if ($StackName -notmatch '^[A-Za-z][A-Za-z0-9-]{0,127}$') { throw 'StackName is invalid.' }
if ($DatabaseBootstrapRevision -notmatch '^[A-Za-z0-9._-]{1,64}$') { throw 'DatabaseBootstrapRevision may contain letters, digits, dots, underscores, and hyphens only.' }
$account = (& aws sts get-caller-identity --region $Region --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0) { throw 'AWS caller identity check failed.' }
$FrontendOrigin = 'https://cloudbox-origin-pending.invalid'
$existingOutputs = & aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs' --output json 2>$null
if ($LASTEXITCODE -eq 0 -and $existingOutputs) {
    $existingCloudFront = ($existingOutputs | ConvertFrom-Json | Where-Object OutputKey -eq 'CloudFrontUrl' | Select-Object -First 1).OutputValue
    if ($existingCloudFront -match '^https://[A-Za-z0-9.-]+$') { $FrontendOrigin = $existingCloudFront }
}
$rawOutputs = & aws cloudformation describe-stacks --stack-name $FoundationStack --region $Region --query 'Stacks[0].Outputs' --output json
if ($LASTEXITCODE -ne 0) { throw 'The CloudBox foundation stack is missing or unreadable. Deploy it first.' }
$outputs = @{}
($rawOutputs | ConvertFrom-Json) | ForEach-Object { $outputs[$_.OutputKey] = $_.OutputValue }
$required = @('DatabaseHost', 'DatabaseSecretArn', 'DatabaseMasterSecretArn', 'LambdaSubnetIds', 'LambdaSecurityGroupId', 'ApiVpcLinkSubnetIds', 'ApiVpcLinkSecurityGroupId', 'BackendListenerArn', 'ApiAuthSecretArn', 'FileArtifactsBucketName')
foreach ($key in $required) { if (-not $outputs.ContainsKey($key) -or -not $outputs[$key]) { throw "Foundation output $key is missing." } }
if ($outputs.Region -ne $Region) { throw "Foundation region mismatch: expected $Region." }
Write-Host "AWS account $account; region $Region; SAM stack $StackName"
Write-Host 'This creates private S3 buckets, API Gateway, four file-operation Lambda functions with separate scoped execution roles, a database bootstrap Lambda and role, and CloudFront behaviors. Review the change set and expected ongoing storage, request, and data-transfer charges.'
& $Sam validate --lint --template-file $Template
if ($LASTEXITCODE -ne 0) { throw 'SAM template validation failed.' }
& $Sam build --template-file $Template
if ($LASTEXITCODE -ne 0) { throw 'SAM build failed.' }
if (-not $Apply) { Write-Host 'Preflight and build complete; no AWS resources were changed. Rerun with -Apply to deploy after reviewing prices and the generated changes.'; return }

$parameters = @(
    "DatabaseHost=$($outputs.DatabaseHost)",
    "DatabaseSecretArn=$($outputs.DatabaseSecretArn)",
    "DatabaseMasterSecretArn=$($outputs.DatabaseMasterSecretArn)",
    'DatabaseUser=cloudbox_app',
    'DatabaseName=cloudbox_db',
    "LambdaSubnetIds=$($outputs.LambdaSubnetIds)",
    "LambdaSecurityGroupId=$($outputs.LambdaSecurityGroupId)",
    "ApiVpcLinkSubnetIds=$($outputs.ApiVpcLinkSubnetIds)",
    "ApiVpcLinkSecurityGroupId=$($outputs.ApiVpcLinkSecurityGroupId)",
    "BackendListenerArn=$($outputs.BackendListenerArn)",
    "AuthTokenSecretArn=$($outputs.ApiAuthSecretArn)",
    "FrontendOrigin=$FrontendOrigin",
    "DatabaseBootstrapRevision=$DatabaseBootstrapRevision"
)
& $Sam deploy --stack-name $StackName --region $Region --s3-bucket $outputs.FileArtifactsBucketName --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --parameter-overrides $parameters --no-confirm-changeset --no-fail-on-empty-changeset
if ($LASTEXITCODE -ne 0) { throw 'SAM deployment failed. Inspect CloudFormation events and do not blindly retry.' }
$stackOutputs = & aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs' --output json | ConvertFrom-Json
$cloudFrontUrl = ($stackOutputs | Where-Object OutputKey -eq 'CloudFrontUrl' | Select-Object -First 1).OutputValue
if ($cloudFrontUrl -notmatch '^https://[A-Za-z0-9.-]+$') { throw 'The application stack did not return a valid HTTPS CloudFront origin.' }
if ($FrontendOrigin -ne $cloudFrontUrl) {
    Write-Host 'Tightening S3 file-bucket CORS to the exact CloudFront website origin.'
    $parameters = @($parameters | Where-Object { $_ -notlike 'FrontendOrigin=*' })
    $parameters += "FrontendOrigin=$cloudFrontUrl"
    & $Sam deploy --stack-name $StackName --region $Region --s3-bucket $outputs.FileArtifactsBucketName --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --parameter-overrides $parameters --no-confirm-changeset --no-fail-on-empty-changeset
    if ($LASTEXITCODE -ne 0) { throw 'The app stack was created, but its exact-origin S3 CORS update failed. Rerun this script after reviewing CloudFormation status.' }
    $FrontendOrigin = $cloudFrontUrl
    $stackOutputs = & aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs' --output json | ConvertFrom-Json
}
Write-Host 'CloudBox application stack outputs:'
$stackOutputs | ForEach-Object { Write-Host "$($_.OutputKey)=$($_.OutputValue)" }
