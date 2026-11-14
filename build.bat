@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "DIR=%~dp0"
set "PY="
set "RC=0"

echo ============================================================
echo   Build VideoSaver.exe  (one-time setup + package)
echo   folder: %DIR%
echo ============================================================
echo.

if not exist "%DIR%build_exe.py" goto NO_SCRIPT

rem --- 1) explicit override ---------------------------------------------
if defined VIDEO_SAVER_PYTHON if exist "%VIDEO_SAVER_PYTHON%" set "PY=%VIDEO_SAVER_PYTHON%"

rem --- 2) python on PATH ------------------------------------------------
if not defined PY (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)

rem --- 3) py launcher ---------------------------------------------------
if not defined PY (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)

rem --- 4) common install locations --------------------------------------
if not defined PY (
  for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
  ) do (
    if not defined PY if exist %%P set "PY=%%~P"
  )
)

if not defined PY goto NO_PY

echo [1/2] Using Python: %PY%
"%PY%" -c "import sys;print('      version',sys.version.split()[0])"
echo.

echo [2/2] Running build_exe.py ...
echo.
%PY% "%DIR%build_exe.py" %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" goto FAIL

echo ============================================================
echo Done. Output is in:  %DIR%dist\VideoSaver
echo Zip that whole folder and send it to anyone.
echo ============================================================
echo.
pause
endlocal
exit /b 0

:NO_PY
set "RC=2"
echo [ERROR] Python not found.
echo.
echo   Install Python 3.10+ from https://www.python.org/downloads/
echo   Tick "Add python.exe to PATH" during setup, then run this file again.
goto FAIL

:NO_SCRIPT
set "RC=3"
echo [ERROR] build_exe.py not found in:
echo   %DIR%
echo Make sure you are running this inside the project folder.
goto FAIL

:FAIL
echo.
echo [FAILED] exit code = %RC%
echo Read the messages above for the reason.
echo.
pause
endlocal
exit /b 1
