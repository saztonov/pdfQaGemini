@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

echo ========================================
echo   pdfQaGemini Backend
echo ========================================
echo.

REM Check if Redis is running
docker ps | findstr redis >nul 2>&1
if errorlevel 1 (
    echo Starting Redis...
    docker start redis >nul 2>&1 || docker run -d -p 6379:6379 --name redis redis:7-alpine
    timeout /t 2 >nul
)
echo Redis: OK

REM Start Worker in new window
echo Starting Worker...
start "pdfQaGemini Worker" cmd /k "cd /d "%~dp0" && if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat && cd server && python run_worker.py"
timeout /t 2 >nul
echo Worker: Started in separate window

REM Start Server in current window
echo Starting Server...
echo.
cd /d "%~dp0server"
python -B -m app.main
pause
