@echo off
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"

if exist "dist\LiveScreenTranslatorPro\LiveScreenTranslatorPro.exe" (
    start "" "dist\LiveScreenTranslatorPro\LiveScreenTranslatorPro.exe"
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo Chua co ban EXE hoac moi truong lap trinh.
    echo Hay dung tron bo thu muc phat hanh LiveScreenTranslatorPro.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m app.main
if errorlevel 1 (
    echo.
    echo LiveScreen Translator Pro da dung do loi. Xem log tai:
    echo %%LOCALAPPDATA%%\LiveScreenTranslatorPro\logs\app.log
    pause
)

