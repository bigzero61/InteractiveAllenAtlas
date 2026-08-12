@echo off
setlocal
cd /d "%~dp0\.."

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

%PY% -m venv .venv
if errorlevel 1 goto fail

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

if not exist "data\cache" mkdir "data\cache"
if not exist "data\uploads" mkdir "data\uploads"

echo Install complete.
echo Run with: run_windows.bat
exit /b 0

:fail
echo Installation failed. Please check that Python 3.10 or newer is installed.
exit /b 1
