@echo off
setlocal enabledelayedexpansion
title AccessReaper v2

echo =======================================================================
echo                     AccessReaper v2 Launcher
echo         Identity and Access Management (IAM) Audit System
echo =======================================================================
echo.

cd /d "%~dp0"

set "BACKEND_DIR=%~dp0backend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "UVICORN_EXE=%VENV_DIR%\Scripts\uvicorn.exe"
set "ALEMBIC_EXE=%VENV_DIR%\Scripts\alembic.exe"

:: 1. Check for system python if venv does not exist
if not exist "%PYTHON_EXE%" (
    echo [*] Virtual environment not found. Checking system Python...
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python 3.11+ is required but was not found in PATH.
        echo Please install Python 3.11 or newer and run this launcher again.
        pause
        exit /b 1
    )

    echo [*] Creating virtual environment at %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: 2. Ensure dependencies are installed
if not exist "%UVICORN_EXE%" (
    echo [*] Installing dependencies from requirements.txt...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    "%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )
)

:: 3. Run database migrations
echo [*] Running database migrations...
set "PYTHONPATH=%BACKEND_DIR%"
"%ALEMBIC_EXE%" -c "%BACKEND_DIR%\alembic.ini" upgrade head
if %errorlevel% neq 0 (
    echo [WARNING] Alembic upgrade reported an issue, initializing schema directly...
    "%PYTHON_EXE%" -c "from app.db.session import init_db; init_db()"
)

:: 4. Seed database if empty
echo [*] Checking database seed data...
"%PYTHON_EXE%" -m app.db.seed

:: 5. Open browser in background after short delay
echo [*] Opening browser to http://localhost:8100/#login...
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8100/#login"

:: 6. Launch Uvicorn server on 127.0.0.1:8100
echo.
echo =======================================================================
echo   AccessReaper v2 is running on http://127.0.0.1:8100
echo   Press Ctrl+C to stop the server.
echo =======================================================================
echo.

cd /d "%BACKEND_DIR%"
"%UVICORN_EXE%" app.main:app --host 127.0.0.1 --port 8100
