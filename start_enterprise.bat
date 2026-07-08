@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   EquiSkill - Enterprise Mode (Docker)
echo ============================================
echo.

:: Check Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker not found. Please install Docker Desktop from:
    echo   https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

:: Check .env exists
if not exist ".env" (
    echo ERROR: .env file not found.
    echo Please copy .env.example to .env and add your API keys.
    pause
    exit /b 1
)

echo Starting MySQL + FastAPI Backend + Streamlit Frontend...
echo This may take a few minutes on first run (downloading images).
echo.

docker-compose up --build -d

if errorlevel 1 (
    echo.
    echo Docker Compose failed. See error above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Services are running!
echo.
echo   Streamlit UI   : http://localhost:8501
echo   FastAPI Docs   : http://localhost:8000/docs
echo ============================================
echo.
echo Opening browser...
timeout /t 3 /nobreak >nul
start "" "http://localhost:8501"

echo.
echo Press any key to STOP all services (docker-compose down)...
pause >nul
docker-compose down
