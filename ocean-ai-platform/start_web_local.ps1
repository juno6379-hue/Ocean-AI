param(
    [ValidateSet('Backend','Frontend')][string]$Service,
    [int]$Port = 0,
    # Existing document/vector workers still own this data. Migration is separate.
    [string]$DocumentDataRoot = 'C:\AI_Observation\ocean-ai-platform\backend\app\data'
)
$ErrorActionPreference = 'Stop'
if ($Service -eq 'Backend') {
    if (-not $Port) { $Port = 8000 }
    if (-not (Test-Path -LiteralPath (Join-Path $DocumentDataRoot 'document_pipeline\contract.json'))) {
        throw 'Existing document contract not found. Supply the verified DocumentDataRoot; do not initialize a replacement index.'
    }
    $env:OCEAN_APP_DATA_DIR = $DocumentDataRoot
    $env:DOCUMENT_PIPELINE_DIR = Join-Path $DocumentDataRoot 'document_pipeline'
    $env:MDC_SYNC_ENABLED = 'false'
    $env:AUTO_CREATE_TABLES = 'false'
    & (Join-Path $PSScriptRoot 'backend\run_local.ps1') -Port $Port
} else {
    if (-not $Port) { $Port = 5173 }
    Set-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
    node node_modules/vite/bin/vite.js --host 127.0.0.1 --port $Port --strictPort --configLoader native
}
exit $LASTEXITCODE
