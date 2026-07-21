$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment was not found at $python"
}

$checkCommand = @"
from pathlib import Path
from dotenv import load_dotenv
from app.llm import check_llm_connection

load_dotenv(Path('.env'))
status = check_llm_connection()
print(status.message)
raise SystemExit(0 if status.available else 1)
"@

Push-Location $projectRoot
try {
    & $python -c $checkCommand
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
