@echo off
cd /d "%~dp0server"
echo ========================================
echo   pdfQaGemini Worker (arq)
echo ========================================
echo.
echo Logs: ..\logs\worker.log
echo.
python run_worker.py
pause
