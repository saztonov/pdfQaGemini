@echo off
cd /d "%~dp0desktop"
echo Starting pdfQaGemini Desktop...
echo Logs: ..\logs\desktop.log
echo.
python -B -m app.main
pause
