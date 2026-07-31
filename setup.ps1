<#
.SYNOPSIS
  Prayash — Windows PowerShell setup & startup script.
.DESCRIPTION
  1. Installs Python dependencies.
  2. Trains / verifies ML model artifacts.
  3. Starts the Flask development server.

  Use -SkipServer to only prepare artifacts without launching the app.
  Use -TrainOnly to rebuild artifacts even if they already exist.
.EXAMPLE
  .\setup.ps1              # Full setup + server start
  .\setup.ps1 -SkipServer  # Dependencies + training only
  .\setup.ps1 -TrainOnly   # Force re-train + dependencies
#>
param(
    [switch]$SkipServer,
    [switch]$TrainOnly
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    # Fall back to system Python if no .venv
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw 'Python not found. Create a virtual environment (.venv) or install Python.'
    }
    $python = $python.Source
}

Write-Host "`n=== Installing dependencies ===" -ForegroundColor Cyan
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw 'pip install failed.'
}

Write-Host "`n=== ML Model Training ===" -ForegroundColor Cyan
$modelExists = (Test-Path "ml_models\model.pkl") -and (Test-Path "ml_models\courses.pkl")
if ($TrainOnly -or -not $modelExists) {
    if ($TrainOnly) {
        Write-Host "Forced re-train requested..." -ForegroundColor Yellow
    } else {
        Write-Host "Model artifacts not found. Training from scratch..." -ForegroundColor Yellow
    }
    & $python train_model.py
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw 'Model training failed.'
    }
} else {
    Write-Host "Model artifacts already exist — skipping training." -ForegroundColor Green
}

Write-Host "`n=== Initializing database ===" -ForegroundColor Cyan
& $python -c "from app import initialize_database; initialize_database()"

if ($SkipServer) {
    Write-Host "`nSetup complete. Run '.\venv\Scripts\python app.py' to start the server." -ForegroundColor Green
} elseif (-not $TrainOnly) {
    Write-Host "`n=== Starting Prayash Flask Server ===" -ForegroundColor Cyan
    & $python app.py
}
