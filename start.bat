@echo off
cd /d "%~dp0"

REM Try venv Python first, then system Python
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" start.py
) else (
    python start.py
)
