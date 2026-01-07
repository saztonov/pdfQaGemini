@echo off
cd /d "%~dp0server"
echo Starting pdfQaGemini Server with auto-reload...
echo Logs: ..\logs\server.log
echo API Docs: http://localhost:8000/docs
echo.
python -B -m app.main
pause
