@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY="
py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if not defined PY (
  python -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3, 12) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python 3.12 is required. Install it from https://www.python.org/downloads/ and tick Add python.exe to PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create .venv
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -c "import psychopy, streamlit, pylsl, aiofiles" >nul 2>&1
if errorlevel 1 (
  echo Installing libraries. The first run takes a few minutes.
  ".venv\Scripts\python.exe" -m pip install -U pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Installation failed.
    pause
    exit /b 1
  )
)

set "SESSION=--dummy-eeg --dummy-gaze"
if /I "%~1"=="live" set "SESSION=--no-dummy-eeg --no-dummy-gaze"

echo Operator: http://localhost:8765
start "Neuro-SE operator" /D "%CD%" ".venv\Scripts\streamlit.exe" run operator_app.py --server.port 8765
timeout /t 3 /nobreak >nul
start "" http://localhost:8765
start "Neuro-SE session" /D "%CD%" ".venv\Scripts\python.exe" -u main.py --line-style mono %SESSION% --lsl --no-fullscreen
endlocal
