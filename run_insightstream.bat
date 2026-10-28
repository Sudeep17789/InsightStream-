@echo off
title InsightStream Setup and Launcher
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo During setup, enable Add Python to PATH.
  pause
  exit /b 1
)
echo Installing InsightStream dependencies. This may take a while.
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation failed. Review the error above.
  pause
  exit /b 1
)
echo Starting InsightStream...
start "InsightStream Server" cmd /k "cd /d ""%~dp0"" && python app.py"
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:5000"
echo Keep the server terminal open while using InsightStream.
pause
