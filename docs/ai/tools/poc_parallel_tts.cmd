@echo off
cd /d S:\Documents\Kilo_Commons\voicebox
backend\venv\Scripts\python.exe docs\ai\tools\poc_parallel_tts.py
echo.
echo Done. Logs: docs\ai\tmp\poc-parallel-tts-*.log / poc-parallel-tts-results.json
pause
