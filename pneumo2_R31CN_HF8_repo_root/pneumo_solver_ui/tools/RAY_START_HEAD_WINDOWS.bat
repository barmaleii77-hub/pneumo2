@echo off
setlocal
echo Starting Ray head on port 6379...
ray start --head --port=6379 --dashboard-host=0.0.0.0
echo Ray head started.
pause
