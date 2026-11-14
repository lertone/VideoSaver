@echo off
setlocal enabledelayedexpansion
set "DIR=%~dp0"
set "PY="
set "RC=0"

echo ============================================================
echo   Video Saver launcher
echo   folder: %DIR%
echo ============================================================
echo.

if not exist "%DIR%launch.py" goto NO_LAUNCH

rem --- 1) user override -------------------------------------------------
if defined VIDEO_SAVER_PYTHON if exist "%VIDEO_SAVER_PYTHON%" set "PY=%VIDEO_SAVER_PYTHON%"

rem --- 2) python on PATH (usually the default install) -----------------
if not defined PY (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)

rem --- 3) official py launcher ------------------------------------------
rem     NOTE: `py -3` picks the newest 3.x, which may differ from the
rem     interpreter this app was tested with, so it is only a fallback.
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

echo Using: %PY%
echo.
%PY% "%DIR%launch.py"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto FAIL

endlocal
exit /b 0

:NO_PY
set "RC=2"
echo [ERROR] Python was not found on this computer.
echo.
echo   Option A: install Python 3.10+ from https://www.python.org/downloads/
echo             (tick "Add python.exe to PATH" during setup), then run this file again.
echo   Option B: use the packaged build instead - VideoSaver.exe needs no Python.
echo.
echo   Already have Python somewhere else? Set the path first:
echo       set VIDEO_SAVER_PYTHON=D:\Python312\python.exe
goto FAIL

:NO_LAUNCH
set "RC=3"
echo [ERROR] launch.py not found in:
echo   %DIR%
echo Make sure you extracted the whole folder, not just start.bat.
goto FAIL

:FAIL
echo.
echo [FAILED] exit code = %RC%
echo Press any key to close this window.
pause >nul
endlocal
exit /b 1
