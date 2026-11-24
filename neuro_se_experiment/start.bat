@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Windows PsychoPy depends on pywinhook, which publishes a binary wheel for
rem Python 3.11 only. Python 3.12 tries to compile it and stops without SWIG.
call :find_python
if not defined PYEXE call :install_python
if not defined PYEXE call :find_python
if not defined PYEXE (
  echo Python 3.11 was not installed. Install Python 3.11.9 from https://www.python.org/downloads/release/python-3119/
  pause
  exit /b 1
)

set "REMAKE="
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3, 11) else 1)" >nul 2>&1
  if errorlevel 1 set "REMAKE=1"
)
if defined REMAKE (
  echo The existing environment is not Python 3.11. Recreating it.
  rmdir /s /q ".venv"
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating the virtual environment...
  "%PYEXE%" -m venv .venv
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
exit /b 0

:find_python
set "PYEXE="
for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
if defined PYEXE exit /b 0
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYEXE if exist "%ProgramFiles%\Python311\python.exe" set "PYEXE=%ProgramFiles%\Python311\python.exe"
exit /b 0

:install_python
echo Installing Python 3.11...
where winget >nul 2>&1
if not errorlevel 1 (
  winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
  call :find_python
  if defined PYEXE exit /b 0
)
echo Downloading the Python 3.11.9 installer...
set "INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
curl.exe -L --fail -o "%INSTALLER%" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
if errorlevel 1 exit /b 1
"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python311\python.exe"
exit /b 0
