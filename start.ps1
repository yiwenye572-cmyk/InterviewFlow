# Always use project venv (system Python lacks dashscope etc.)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Uvicorn = Join-Path $Root ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

if (-not (Test-Path $Uvicorn)) {
    Write-Host "Installing dependencies..."
    & $Python -m pip install -r requirements.txt
}

Write-Host "Starting server at http://127.0.0.1:8000"
& $Uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
