param(
    [Parameter(Mandatory = $true)][string]$UploadUrlFunction,
    [Parameter(Mandatory = $true)][string]$ConfirmUploadFunction,
    [Parameter(Mandatory = $true)][string]$DownloadUrlFunction,
    [Parameter(Mandatory = $true)][string]$DeleteFileFunction,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$Region = 'ap-southeast-2'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$LambdaRoot = Join-Path $ProjectRoot 'lambda'
$PackageRoot = Join-Path $PSScriptRoot 'out\lambda'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$functions = @(
    @{ Handler = 'upload_url'; Name = $UploadUrlFunction },
    @{ Handler = 'confirm_upload'; Name = $ConfirmUploadFunction },
    @{ Handler = 'download_url'; Name = $DownloadUrlFunction },
    @{ Handler = 'delete_file'; Name = $DeleteFileFunction }
)
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 was not found in PATH.' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'CloudBox .venv is missing. Install the declared requirements before packaging.' }
foreach ($name in @($UploadUrlFunction, $ConfirmUploadFunction, $DownloadUrlFunction, $DeleteFileFunction)) {
    if ($name -notmatch '^[A-Za-z0-9_-]{1,64}$') { throw 'Lambda function names may contain letters, digits, underscores, and hyphens only.' }
}
$account = (& aws sts get-caller-identity --region $Region --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0) { throw 'AWS caller identity check failed.' }
Write-Host "AWS account $account; region $Region"
Write-Host 'This operation updates code only for four named existing Lambda functions; it does not create functions or change configuration.'
if (-not $Apply) { Write-Host 'Preflight only. Rerun with -Apply to package and update the function code.'; return }

New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null
foreach ($item in $functions) {
    if (-not (Test-Path (Join-Path $LambdaRoot $item.Handler))) { throw "Handler package missing: $($item.Handler)" }
    $stage = Join-Path $PackageRoot "$($item.Handler)-$([guid]::NewGuid().ToString('N'))"
    $zipPath = Join-Path $PackageRoot "$($item.Handler)-$([guid]::NewGuid().ToString('N')).zip"
    New-Item -ItemType Directory -Path $stage | Out-Null
    Copy-Item -LiteralPath (Join-Path $LambdaRoot $item.Handler) -Destination $stage -Recurse
    Copy-Item -LiteralPath (Join-Path $LambdaRoot 'common') -Destination $stage -Recurse
    & $Python -m pip install --disable-pip-version-check --no-warn-script-location --target $stage -r (Join-Path $LambdaRoot 'requirements.txt') | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Lambda dependencies could not be packaged for $($item.Handler)." }
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal
    & aws lambda update-function-code --function-name $item.Name --zip-file "fileb://$zipPath" --region $Region --no-cli-pager | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Lambda code update failed for $($item.Name)." }
    Write-Host "Updated code for $($item.Name). Verify its LastUpdateStatus before use."
}
