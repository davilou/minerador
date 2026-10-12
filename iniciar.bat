@echo off
cd /d "%~dp0"
start "" http://localhost:8765
.venv\Scripts\python -m uvicorn app:app --port 8765
