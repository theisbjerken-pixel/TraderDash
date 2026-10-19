while (Get-Process msedge -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 3
}

Start-Sleep -Seconds 2
& "C:\Users\tb\TraderDash\.venv\Scripts\python.exe" "C:\Users\tb\TraderDash\add-edge-favorite.py"
