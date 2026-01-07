@echo off
cd /d "%~dp0server"
echo Starting pdfQaGemini Server...
echo Logs: ..\logs\server.log
echo Check .env for HOST and PORT settings
echo.
python -B -m app.main
pause
