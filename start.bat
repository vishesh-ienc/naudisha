@echo off
echo Starting NauDisha Full-Stack Application...
start "NauDisha Backend (FastAPI)" cmd /k "cd /d %~dp0 && python -m uvicorn naudisha.api.main:app --host 127.0.0.1 --port 8000 --reload"
start "NauDisha Frontend (Vite)" cmd /k "cd /d %~dp0frontend && npm run dev"
echo Backend running at http://127.0.0.1:8000
echo Frontend running at http://localhost:5173
