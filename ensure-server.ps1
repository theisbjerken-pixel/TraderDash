$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8501
$url = "http://127.0.0.1:$port"

function Show-DashboardMessage {
    param([string]$Message)
    $shell = New-Object -ComObject Wscript.Shell
    $shell.Popup($Message, 0, "TraderDash", 48) | Out-Null
}

function Get-GitExe {
    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $fallback = Join-Path $env:LOCALAPPDATA "Programs\Git\cmd\git.exe"
    if (Test-Path $fallback) {
        return $fallback
    }
    return $null
}

function Update-LocalRepoFromGitHub {
    $git = Get-GitExe
    if (-not $git) {
        Show-DashboardMessage "Git blev ikke fundet, så TraderDash starter med den lokale kopi."
        return $false
    }

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $before = & $git -C $root rev-parse HEAD
        if ($LASTEXITCODE -ne 0) {
            Show-DashboardMessage "Den lokale mappe er ikke et git-arkiv, så TraderDash starter med den lokale kopi."
            return $false
        }

        & $git -C $root pull --ff-only origin master *> $null
        if ($LASTEXITCODE -ne 0) {
            Show-DashboardMessage "Kunne ikke hente den seneste version fra GitHub. TraderDash starter med den lokale kopi."
            return $false
        }

        $after = & $git -C $root rev-parse HEAD
        return "$before" -ne "$after"
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Stop-DashboardListener {
    $lines = netstat -ano | Select-String -Pattern "127\.0\.0\.1:$port\s+.*LISTENING"
    foreach ($line in $lines) {
        $processId = ($line.ToString().Trim() -split "\s+")[-1]
        if ($processId -match "^\d+$" -and $processId -ne "0") {
            Stop-Process -Id ([int]$processId) -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 400
}

function Test-DashboardPort {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $wait = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        $connected = $wait.AsyncWaitHandle.WaitOne(400)
        if (-not $connected) {
            return $false
        }
        $client.EndConnect($wait)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-DashboardPage {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

$updatedFromGitHub = Update-LocalRepoFromGitHub
if ($updatedFromGitHub) {
    Stop-DashboardListener
}

if (-not (Test-DashboardPort)) {
    $streamlit = Join-Path $root ".venv\Scripts\streamlit.exe"
    if (-not (Test-Path $streamlit)) {
        Show-DashboardMessage "Python-miljøet mangler (.venv). Åbn mappen C:\Users\tb\TraderDash i Cursor, så kan den sættes op igen."
        exit 1
    }
    Start-Process -FilePath $streamlit -ArgumentList @(
        "run", "app.py",
        "--server.headless", "true",
        "--server.port", "$port",
        "--server.address", "127.0.0.1",
        "--browser.gatherUsageStats", "false"
    ) -WorkingDirectory $root -WindowStyle Hidden
}

$deadline = (Get-Date).AddSeconds(45)
do {
    if (Test-DashboardPage) {
        exit 0
    }
    Start-Sleep -Milliseconds 400
} while ((Get-Date) -lt $deadline)

exit 1
