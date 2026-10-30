$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root "ensure-server.ps1")
if ($LASTEXITCODE -ne 0) {
    $shell = New-Object -ComObject Wscript.Shell
    $shell.Popup("TraderDash kunne ikke starte. Tjek at Git og .venv er på plads i C:\Users\tb\TraderDash.", 0, "TraderDash", 48) | Out-Null
    exit 1
}

$edge = Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edge)) {
    $edge = Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"
}
Start-Process -FilePath $edge -ArgumentList "http://localhost:8501"
