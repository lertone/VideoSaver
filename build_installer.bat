@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "DIR=%~dp0"
set "PY="
set "SRC=%~1"

echo ============================================================
echo   Build Windows installer (Setup.exe)
echo   folder: %DIR%
echo ============================================================
echo.

if not exist "%DIR%build_installer.py" goto NO_SCRIPT

if defined VIDEO_SAVER_PYTHON if exist "%VIDEO_SAVER_PYTHON%" set "PY=%VIDEO_SAVER_PYTHON%"
if not defined PY (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY goto NO_PY

rem 默认打包 dist\VideoSaver；第一个参数可换成别的目录
if not defined SRC set "SRC=dist\VideoSaver"

echo [1/1] Compiling installer from: %SRC%
echo.
if defined SRC (
  %PY% "%DIR%build_installer.py" --src "%SRC%"
) else (
  %PY% "%DIR%build_installer.py"
)
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" goto FAIL

echo Output folder: %DIR%installer_out
echo.
pause
endlocal
exit /b 0

:NO_PY
echo [ERROR] Python not found. Install Python 3.10+ and try again.
goto FAIL

:NO_SCRIPT
echo [ERROR] build_installer.py not found in:
echo   %DIR%
goto FAIL

:FAIL
echo.
echo [FAILED] exit code = %RC%
echo Read the messages above. Common causes:
echo   1) Inno Setup not installed:  winget install --id JRSoftware.InnoSetup
echo   2) dist folder missing:       run build.bat first
echo.
pause
endlocal
exit /b 1
