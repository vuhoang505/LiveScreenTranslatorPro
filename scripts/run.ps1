$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$exePath = Join-Path $projectRoot "dist\LiveScreenTranslatorPro\LiveScreenTranslatorPro.exe"
$env:PYTHONUTF8 = "1"

if (Test-Path $exePath) {
    if (Get-Process -Name "LiveScreenTranslatorPro" -ErrorAction SilentlyContinue) {
        Write-Host "LiveScreen Translator Pro dang chay." -ForegroundColor Yellow
        exit 0
    }
    Start-Process -FilePath $exePath `
        -WorkingDirectory (Split-Path -Parent $exePath) `
        -WindowStyle Normal
    Write-Host "LiveScreen Translator Pro da duoc mo." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $pythonPath)) {
    throw "Chưa có bản EXE hoặc .venv. Hãy dùng đầy đủ thư mục phát hành."
}

Push-Location $projectRoot
try {
    & $pythonPath -c "import PySide6" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Thiếu dependencies. Hãy chạy .\scripts\setup.ps1."
    }
    & $pythonPath -m app.main
} finally {
    Pop-Location
}

