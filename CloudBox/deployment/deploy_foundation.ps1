param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$Region = 'ap-southeast-2'
$StackName = 'cloudbox-foundation'
$Template = Join-Path $PSScriptRoot 'foundation.yaml'
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 was not found in PATH.' }
$account = (& aws sts get-caller-identity --region $Region --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0) { throw 'AWS caller identity check failed.' }
$stackStatus = & aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].StackStatus' --output text 2>$null
if ($LASTEXITCODE -eq 0 -and $stackStatus -and $stackStatus -ne 'None') { throw "Stack $StackName already exists with status $stackStatus. Review it before any update; this script creates only a new stack." }
Write-Host "AWS account $account; region $Region; new stack $StackName"
Write-Host 'This creates a VPC, EC2 with public IPv4 but no public inbound rules, an internal NLB and API Gateway VPC Link target, private encrypted RDS MySQL, Secrets Manager and S3 endpoints, an artifact bucket, IAM roles, and generated secrets. EC2, NLB, endpoint, and RDS charges may continue while idle; RDS deletion retains a billable snapshot.'
if (-not $Apply) { Write-Host 'Preflight only. Review deployment/README.md and current prices. Rerun with -Apply to create the stack.'; return }

& aws cloudformation create-stack --stack-name $StackName --template-body "file://$Template" --capabilities CAPABILITY_IAM --region $Region --tags Key=Project,Value=CloudBox
if ($LASTEXITCODE -ne 0) { throw 'CloudFormation rejected the create-stack request. Inspect the exact AWS error and stack events before retrying.' }
& aws cloudformation wait stack-create-complete --stack-name $StackName --region $Region
if ($LASTEXITCODE -ne 0) { throw "Foundation stack did not reach CREATE_COMPLETE. Inspect CloudFormation stack events; do not blindly retry." }
$outputs = & aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs' --output json | ConvertFrom-Json
Write-Host 'Foundation stack outputs:'
$outputs | ForEach-Object { Write-Host "$($_.OutputKey)=$($_.OutputValue)" }
