@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Please run setup_windows.bat first.
    pause
    exit /b 1
)

echo Launching EquiSkill...
".venv\Scripts\python.exe" -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo Streamlit exited with an error - see the message above.
    pause
)
