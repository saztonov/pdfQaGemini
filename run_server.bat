@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
cd /d "%~dp0server"
echo ========================================
echo   pdfQaGemini Server (API)
echo ========================================
echo.
echo IMPORTANT: Before starting, ensure:
echo   1. Redis is running: docker run -d -p 6379:6379 --name redis redis:7-alpine
echo   2. Worker is running: run_worker.bat (in separate terminal)
echo.
echo Logs: ..\logs\server.log
echo.
python -B -m app.main
pause
