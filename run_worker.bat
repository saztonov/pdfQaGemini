@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
cd /d "%~dp0server"
echo ========================================
echo   pdfQaGemini Worker (arq)
echo ========================================
echo.
echo Logs: ..\logs\worker.log
echo.
python run_worker.py
pause
