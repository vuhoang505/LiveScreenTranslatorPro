[CmdletBinding()]
param(
    [switch]$SkipTests
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
    & $pythonPath -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Không thể cài build dependencies." }
    if (-not $SkipTests) {
        $env:QT_QPA_PLATFORM = "offscreen"
        & $pythonPath -m pytest
        if ($LASTEXITCODE -ne 0) { throw "Tests thất bại; đã hủy build." }
    }
    & $pythonPath -m PyInstaller `
        --noconfirm `
        --clean `
        --debug bootloader `
        --windowed `
        --name "LiveScreenTranslatorPro" `
        --icon "app\resources\icons\app-icon.ico" `
        --add-data "app\resources\icons\app-icon.ico;app\resources\icons" `
        --add-data "app\resources\models;app\resources\models" `
        --additional-hooks-dir "packaging\hooks" `
        --paths $projectRoot `
        app\main.py
    if ($LASTEXITCODE -ne 0 -and (Test-Path "LiveScreenTranslatorPro.spec")) {
        Write-Host "Build bi khoa file tam; dang thu lai buoc dong goi..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
        & $pythonPath -m PyInstaller --noconfirm ".\LiveScreenTranslatorPro.spec"
    }
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build thất bại." }
    Write-Host "EXE: $projectRoot\dist\LiveScreenTranslatorPro\LiveScreenTranslatorPro.exe" -ForegroundColor Green
} finally {
    Pop-Location
}

