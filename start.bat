@echo off
echo Starting AI ID Card Scanner...

echo Starting FastAPI Backend (Port 8000)...
start cmd /k "python -m uvicorn backend.main:app --reload --port 8000"

echo Starting Frontend Server (Port 3000)...
cd frontend
start cmd /k "python -m http.server 3000"

echo Servers started!
echo Frontend: http://localhost:3000
echo Backend API: http://localhost:8000
