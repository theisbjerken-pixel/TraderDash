$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8501
$url = "http://127.0.0.1:$port"

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

if (-not (Test-DashboardPort)) {
    $streamlit = Join-Path $root ".venv\Scripts\streamlit.exe"
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
