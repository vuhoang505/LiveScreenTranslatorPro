[CmdletBinding()]
param(
    [ValidateSet("en", "ch", "japan", "korean")]
    [string]$Language = "en",
    [ValidateSet("PP-OCRv5_mobile", "PP-OCRv5_server")]
    [string]$Model = "PP-OCRv5_mobile"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$env:PYTHONUTF8 = "1"

if (-not (Test-Path $pythonPath)) {
    throw "Chưa có .venv. Hãy chạy .\scripts\setup.ps1 -Dev trước."
}

Push-Location $projectRoot
try {
    & $pythonPath -m app.ocr.model_manager --language $Language --model $Model
    if ($LASTEXITCODE -ne 0) { throw "Tải/khởi tạo model OCR thất bại." }
} finally {
    Pop-Location
}

