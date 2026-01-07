@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

echo ========================================
echo   pdfQaGemini Desktop App
echo ========================================
echo.
echo Logs: logs\desktop.log
echo.

cd /d "%~dp0desktop"
python -B -m app.main
pause
