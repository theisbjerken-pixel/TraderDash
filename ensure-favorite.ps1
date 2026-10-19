$edge = Get-Process msedge -ErrorAction SilentlyContinue
if ($edge) {
    exit 0
}

& "C:\Users\tb\TraderDash\.venv\Scripts\python.exe" "C:\Users\tb\TraderDash\add-edge-favorite.py"
