param([int]$Port = 8000, [switch]$Reload)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

# Prefer the installed requirement. This workstation also has a previously
# installed offline DuckDB distribution; reuse it without downloading packages.
$env:PYTHONPATH = $PSScriptRoot
python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('duckdb') else 1)"
if ($LASTEXITCODE -ne 0) {
    $lakeVendor = 'D:\AI_Observation\work\nullable_timeseries\vendor'
    if (-not (Test-Path -LiteralPath "$lakeVendor\duckdb")) {
        throw 'DuckDB dependency missing. Install backend/requirements.txt in this Python environment.'
    }
    $env:PYTHONPATH = "$PSScriptRoot;$lakeVendor"
}
$env:PYTHONIOENCODING = 'utf-8'
$serverArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port")
if ($Reload) { $serverArgs += '--reload' }
python @serverArgs
exit $LASTEXITCODE
