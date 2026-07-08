@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===============================================
echo  EquiSkill setup
echo ===============================================

REM --- Find a Python interpreter in the 3.9-3.12 range. -------------------
REM Newer Pythons (3.13+) don't yet have prebuilt wheels for some pinned
REM packages here, which forces pip to compile numpy from source and fail
REM without a C compiler installed. Prefer the Windows "py" launcher so we
REM can target a specific compatible version even if a newer Python is the
REM system default.

set "PYCMD="

where py >nul 2>nul
if not errorlevel 1 (
    for %%V in (3.12 3.11 3.10 3.9) do (
        if not defined PYCMD (
            py -%%V --version >nul 2>nul
            if not errorlevel 1 set "PYCMD=py -%%V"
        )
    )
)

if not defined PYCMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; exit(0 if (3,9) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYCMD=python"
    )
)

if not defined PYCMD (
    echo ERROR: Could not find a Python 3.9-3.12 installation.
    echo.
    echo This project's dependencies ^(streamlit, langchain, numpy^) don't yet
    echo have prebuilt Windows wheels for the newest Python releases, which
    echo causes pip to try compiling them from source and fail.
    echo.
    echo Please install Python 3.11 from:
    echo   https://www.python.org/downloads/release/python-3119/
    echo ^(scroll to "Windows installer (64-bit)"^), tick "Add python.exe to PATH"
    echo during install, then run this script again.
    echo.
    echo If you already have Python 3.11 or 3.12 installed alongside a newer
    echo version, make sure it was installed with the "py launcher" option
    echo checked so this script can find it via "py -3.11".
    pause
    exit /b 1
)

echo Using: 
%PYCMD% --version

if exist ".venv" (
    echo Removing existing .venv to avoid reusing a previous, possibly broken install...
    rmdir /s /q ".venv"
)

echo Creating virtual environment in .venv ...
%PYCMD% -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create the virtual environment. See the message above.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv\Scripts\python.exe was not created. Something went wrong above.
    pause
    exit /b 1
)

echo Installing dependencies with the venv's own pip (this can take a few minutes)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Scroll up to see which package failed.
    pause
    exit /b 1
)

echo Verifying Streamlit installed correctly...
".venv\Scripts\python.exe" -m streamlit --version
if errorlevel 1 (
    echo ERROR: Streamlit did not install correctly into .venv.
    pause
    exit /b 1
)

if not exist ".env" (
    copy .env.example .env >nul
    echo.
    echo A .env file has been created for you.
    echo Opening it in Notepad - paste your Gemini API key and save.
    notepad .env
)

echo.
echo ===============================================
echo  Setup complete. Run start_app.bat to launch EquiSkill.
echo ===============================================
pause
