param(
    [switch]$SkipServer
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    throw 'Python virtual environment not found. Create .venv first.'
}

& $python -m pip install -r requirements.txt
& $python evaluation.py
& $python train_model.py
& $python -c "from app import initialize_database; initialize_database()"

if (-not $SkipServer) {
    & $python app.py
}
