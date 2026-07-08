@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Please run setup_windows.bat first.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   EquiSkill - GenAI Career Assistant
echo ============================================
echo.
echo Starting app... Your browser will open at:
echo   http://localhost:8501
echo.
echo Press Ctrl+C to stop the server.
echo.

start "" "http://localhost:8501"
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true

if errorlevel 1 (
    echo.
    echo Streamlit exited with an error - see the message above.
    pause
)
