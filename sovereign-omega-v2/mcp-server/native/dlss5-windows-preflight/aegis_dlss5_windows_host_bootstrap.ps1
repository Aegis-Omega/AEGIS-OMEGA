[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$CandidateSha,

    [string]$OutputPath = (Join-Path $PWD 'aegis-dlss5-windows-host-bootstrap-receipt.json'),

    [string]$WorkDir = (Join-Path ([System.IO.Path]::GetTempPath()) 'aegis-dlss5-bootstrap')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$StreamlineSourceSha = '2122257e0fce486f91b385aa63b9a09b0a34b363'
$StreamlineReleaseSha256 = '92c4d954631a1710da86ca3fa8d5034f2b9503838c95fc4ae977ae149319781b'
$StreamlineReleaseUrl = 'https://github.com/NVIDIA-RTX/Streamline/releases/download/v2.14.1/streamline-sdk-v2.14.1.zip'
$Schema = 'AEGIS_DLSS5_WINDOWS_HOST_BOOTSTRAP_RECEIPT_V1'

function Get-Sha256Text {
    param([Parameter(Mandatory = $true)][string]$Text)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
    return ([System.Convert]::ToHexString($hash)).ToLowerInvariant()
}

function Write-BoundedReceipt {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [string]$GpuName = '',
        [string]$DriverVersion = '',
        [string]$ReasonCode = '',
        [bool]$SdkDigestVerified = $false,
        [string]$SdkArchivePath = ''
    )

    $body = [ordered]@{
        schema = $Schema
        status = $Status
        candidate_sha = $CandidateSha.ToLowerInvariant()
        captured_at = [DateTimeOffset]::UtcNow.ToString('o')
        host_os = [System.Environment]::OSVersion.VersionString
        gpu_name = $GpuName
        driver_version = $DriverVersion
        reason_code = $ReasonCode
        streamline_source_sha = $StreamlineSourceSha
        streamline_release_sha256 = $StreamlineReleaseSha256
        streamline_release_url = $StreamlineReleaseUrl
        sdk_digest_verified = $SdkDigestVerified
        sdk_archive_path = $SdkArchivePath
        feature_symbol = 'sl::kFeatureDLSS_NR'
        feature_id = 1004
        support_api = 'slIsFeatureSupported'
        support_query_executed = $false
        evaluation_executed = $false
        runtime_claim = 'NOT_ESTABLISHED'
        rendering_claim = 'NOT_ESTABLISHED'
        quality_claim = 'NOT_ESTABLISHED'
        execution_release = 'BLOCKED_PENDING_SUPPORT_QUERY'
        claim_promotion = 'BLOCKED'
        authority_effect = 'NONE'
    }

    $canonicalBody = $body | ConvertTo-Json -Depth 8 -Compress
    $body.receipt_digest = 'sha256:' + (Get-Sha256Text -Text $canonicalBody)
    $json = $body | ConvertTo-Json -Depth 8

    $outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
    $outputDirectory = Split-Path -Parent $outputFullPath
    if ($outputDirectory) {
        New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    }
    [System.IO.File]::WriteAllText($outputFullPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Output $json
}

if ($env:OS -ne 'Windows_NT') {
    Write-BoundedReceipt -Status 'HOST_UNSUPPORTED' -ReasonCode 'WINDOWS_REQUIRED'
    exit 20
}

$nvidiaSmi = Get-Command 'nvidia-smi.exe' -ErrorAction SilentlyContinue
if (-not $nvidiaSmi) {
    $nvidiaSmi = Get-Command 'nvidia-smi' -ErrorAction SilentlyContinue
}
if (-not $nvidiaSmi) {
    Write-BoundedReceipt -Status 'HOST_UNSUPPORTED' -ReasonCode 'NVIDIA_SMI_MISSING'
    exit 21
}

$gpuRows = @(& $nvidiaSmi.Source '--query-gpu=name,driver_version' '--format=csv,noheader')
if ($LASTEXITCODE -ne 0 -or $gpuRows.Count -eq 0) {
    Write-BoundedReceipt -Status 'HOST_UNSUPPORTED' -ReasonCode 'NVIDIA_SMI_QUERY_FAILED'
    exit 22
}

$eligibleGpu = $null
foreach ($row in $gpuRows) {
    $parts = $row -split ',', 2
    if ($parts.Count -ne 2) { continue }
    $name = $parts[0].Trim()
    $driver = $parts[1].Trim()
    if ($name -match '(?i)GeForce\s+RTX\s+50') {
        $eligibleGpu = [pscustomobject]@{ Name = $name; Driver = $driver }
        break
    }
}

if (-not $eligibleGpu) {
    $observed = ($gpuRows -join '; ').Trim()
    Write-BoundedReceipt -Status 'HOST_UNSUPPORTED' -GpuName $observed -ReasonCode 'GEFORCE_RTX50_REQUIRED'
    exit 23
}

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$archivePath = Join-Path $WorkDir 'streamline-sdk-v2.14.1.zip'

if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}

Invoke-WebRequest -Uri $StreamlineReleaseUrl -OutFile $archivePath
$actualArchiveSha = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualArchiveSha -ne $StreamlineReleaseSha256) {
    Write-BoundedReceipt `
        -Status 'SDK_DENIED' `
        -GpuName $eligibleGpu.Name `
        -DriverVersion $eligibleGpu.Driver `
        -ReasonCode 'STREAMLINE_DIGEST_MISMATCH' `
        -SdkDigestVerified $false `
        -SdkArchivePath ([System.IO.Path]::GetFullPath($archivePath))
    exit 24
}

Write-BoundedReceipt `
    -Status 'HOST_ELIGIBLE_FOR_SUPPORT_QUERY' `
    -GpuName $eligibleGpu.Name `
    -DriverVersion $eligibleGpu.Driver `
    -ReasonCode '' `
    -SdkDigestVerified $true `
    -SdkArchivePath ([System.IO.Path]::GetFullPath($archivePath))

exit 0
