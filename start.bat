@echo off
title DuplexVani Server
echo ==========================================
echo Starting DuplexVani Full-Duplex Server...
echo URL: http://127.0.0.1:8000
echo ==========================================
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
