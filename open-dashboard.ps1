$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root "ensure-server.ps1")

$edge = Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edge)) {
    $edge = Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"
}
Start-Process -FilePath $edge -ArgumentList "http://localhost:8501"
