@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
cd /d "%~dp0desktop"
echo Starting pdfQaGemini Desktop...
echo Logs: ..\logs\desktop.log
echo.
python -B -m app.main
pause
