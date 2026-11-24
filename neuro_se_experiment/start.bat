@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Windows PsychoPy depends on pywinhook, which publishes a binary wheel for
rem Python 3.11 only. Python 3.12 tries to compile it and stops without SWIG.
call :find_python
if not defined PYEXE (
  echo Could not find the Python 3.11 that is already installed.
  echo In this window run: py -0p
  pause
  exit /b 1
)
echo Using the installed Python 3.11: %PYEXE%

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

set "NEURO_SE_AUTOSTART=1"
if /I "%~1"=="live" set "NEURO_SE_LIVE_DEFAULT=1"

echo Operator: http://localhost:8765
start "Neuro-SE operator" /D "%CD%" ".venv\Scripts\streamlit.exe" run operator_app.py --server.port 8765
timeout /t 3 /nobreak >nul
start "" http://localhost:8765
endlocal
exit /b 0

:find_python
set "PYEXE="
for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
if defined PYEXE exit /b 0
call :from_reg "HKCU\Software\Python\PythonCore\3.11\InstallPath"
if defined PYEXE exit /b 0
call :from_reg "HKLM\Software\Python\PythonCore\3.11\InstallPath"
if defined PYEXE exit /b 0
call :from_reg "HKCU\Software\Python\PythonCore\3.11-64\InstallPath"
if defined PYEXE exit /b 0
call :from_reg "HKLM\Software\Python\PythonCore\3.11-64\InstallPath"
if defined PYEXE exit /b 0
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYEXE if exist "%ProgramFiles%\Python311\python.exe" set "PYEXE=%ProgramFiles%\Python311\python.exe"
if not defined PYEXE if exist "C:\Python311\python.exe" set "PYEXE=C:\Python311\python.exe"
if defined PYEXE exit /b 0
for /f "delims=" %%I in ('where python 2^>nul') do call :consider "%%I"
exit /b 0

:from_reg
for /f "skip=2 tokens=1,2*" %%A in ('reg query "%~1" /v ExecutablePath 2^>nul') do (
  if /I "%%A"=="ExecutablePath" set "PYEXE=%%C"
)
exit /b 0

:consider
if defined PYEXE exit /b 0
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3, 11) else 1)" >nul 2>&1 || exit /b 0
set "PYEXE=%~1"
exit /b 0
