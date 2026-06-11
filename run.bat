@echo off
cd /d %~dp0
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo Please create venv first: python -m venv .venv
    exit /b 1
)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
