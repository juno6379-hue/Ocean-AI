param(
    [string]$PythonPath = 'D:\AI_Observation\work\current-implementation-venv-20261008\Scripts\python.exe',
    [string]$DeploymentRoot = 'D:\AI_Observation\outputs\train-deploy-20261008\deployment'
)
$ErrorActionPreference = 'Stop'
$backendRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$deploymentPath = [System.IO.Path]::GetFullPath($DeploymentRoot)
if (Get-NetTCPConnection -LocalPort 8011 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8011 already has a listener; existing processes were preserved.'
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Python executable does not exist.' }
New-Item -ItemType Directory -Path $deploymentPath -Force | Out-Null
$stdout = Join-Path $deploymentPath 'server.stdout.log'
$stderr = Join-Path $deploymentPath 'server.stderr.log'
$arguments = @('-B', '-m', 'app.scripts.raw_forecast_development_server', '--deployment-root', ('"' + $deploymentPath + '"'))
$process = Start-Process -FilePath $PythonPath -ArgumentList $arguments -WorkingDirectory $backendRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$listenerPid = $null
for ($attempt = 0; $attempt -lt 5; $attempt++) {
    $listening = Get-NetTCPConnection -LocalPort 8011 -State Listen -ErrorAction SilentlyContinue
    if ($listening) {
        $listenerProcess = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $listening.OwningProcess)
        if ($listenerProcess.CommandLine -like '*app.scripts.raw_forecast_development_server*' -and ($listenerProcess.ProcessId -eq $process.Id -or $listenerProcess.ParentProcessId -eq $process.Id)) {
            $listenerPid = $listenerProcess.ProcessId
        }
        break
    }
    Start-Sleep -Milliseconds 200
}
$receipt = [ordered]@{
    schema_version = 'experimental-server-launch-v1'
    started_at = [DateTimeOffset]::UtcNow.ToString('o')
    pid = $process.Id
    launcher_pid = $process.Id
    listener_pid = $listenerPid
    host = '127.0.0.1'
    port = 8011
    deployment_root = $deploymentPath
    stdout_path = $stdout
    stderr_path = $stderr
    experimental = $true
    nonoperational = $true
    approved = $false
    production_eligible = $false
    canonical_processes_stopped = $false
}
$receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $deploymentPath 'launch-receipt.json') -Encoding UTF8
$receipt | ConvertTo-Json -Depth 4
