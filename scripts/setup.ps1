[CmdletBinding()]
param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
$tempPath = Join-Path $projectRoot ".tmp"

$env:PYTHONUTF8 = "1"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
New-Item -ItemType Directory -Force -Path $tempPath | Out-Null
$env:TEMP = $tempPath
$env:TMP = $tempPath

if (-not (Test-Path $pythonPath)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) {
        throw "Không tìm thấy Python Launcher (py). Hãy cài Python 3.11 hoặc 3.12."
    }
    $available = & py -0p
    if ($available -match "-V:3\.12") {
        & py -3.12 -m venv $venvPath
    } elseif ($available -match "-V:3\.11") {
        & py -3.11 -m venv $venvPath
    } else {
        throw "Cần Python 3.11 hoặc 3.12. Python 3.13 chưa được chọn vì rủi ro tương thích OCR."
    }
}

& $pythonPath -m pip --version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $pythonPath -m ensurepip --upgrade --default-pip
    if ($LASTEXITCODE -ne 0) { throw "Không thể khởi tạo pip bên trong .venv." }
}

& $pythonPath -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Không thể nâng cấp pip bên trong .venv." }
$requirements = if ($Dev) { "requirements-dev.txt" } else { "requirements.txt" }
& $pythonPath -m pip install -r (Join-Path $projectRoot $requirements)
if ($LASTEXITCODE -ne 0) { throw "Cài dependencies thất bại." }

Write-Host ""
Write-Host "Thiết lập hoàn tất: $pythonPath" -ForegroundColor Cyan
Write-Host "Chạy ứng dụng: .\scripts\run.ps1" -ForegroundColor Green

