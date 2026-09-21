@echo off
setlocal
title Nivara - Startup

REM ============================================================
REM Nivara Startup Script
REM Backend: FastAPI
REM Frontend: React + Vite
REM Database: Supabase PostgreSQL (configured in backend .env)
REM ============================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo ============================================================
echo                    NIVARA STARTUP
echo ============================================================
echo.

REM ---- Check backend virtual environment ----
if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo [ERROR] Backend virtual environment not found:
    echo         %ROOT%.venv
    echo.
    echo Create it with:
    echo         py -3.12 -m venv .venv
    echo.
    pause
    exit /b 1
)

REM ---- Check frontend ----
if not exist "%ROOT%frontend\package.json" (
    echo [ERROR] Frontend not found at:
    echo         %ROOT%frontend
    echo.
    pause
    exit /b 1
)

REM ---- Check frontend dependencies ----
if not exist "%ROOT%frontend\node_modules" (
    echo [INFO] frontend\node_modules not found.
    echo [INFO] Installing frontend dependencies...
    cd /d "%ROOT%frontend"
    call npm install
    if errorlevel 1 (
        echo.
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
    cd /d "%ROOT%"
)

echo [1/3] Starting Nivara FastAPI backend...
start "Nivara Backend - FastAPI" cmd /k "cd /d ""%ROOT%"" && .venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Nivara React frontend...
start "Nivara Frontend - Vite" cmd /k "cd /d ""%ROOT%frontend"" && npm run dev -- --host 127.0.0.1"

timeout /t 5 /nobreak >nul

echo [3/3] Opening Nivara...
start "" "http://localhost:5173"

echo.
echo ============================================================
echo Nivara is starting.
echo.
echo Frontend : http://localhost:5173
echo Backend  : http://127.0.0.1:8000
echo API Docs : http://127.0.0.1:8000/docs
echo.
echo Keep the two terminal windows open while using Nivara.
echo Close those windows to stop the application.
echo ============================================================
echo.
exit /b 0
