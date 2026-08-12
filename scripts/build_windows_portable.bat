@echo off
setlocal
cd /d "%~dp0\.."

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

if not exist ".venv" (
  call scripts\install_windows.bat
  if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

".venv\Scripts\pyinstaller.exe" --clean --noconfirm InteractiveAtlas.spec
if errorlevel 1 exit /b 1

if not exist "release" mkdir "release"
if exist "release\InteractiveAtlas_Windows_Portable" rmdir /s /q "release\InteractiveAtlas_Windows_Portable"
xcopy /E /I /Y "dist\InteractiveAtlas" "release\InteractiveAtlas_Windows_Portable"
copy /Y "README.md" "release\InteractiveAtlas_Windows_Portable\README.md" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'release\InteractiveAtlas_Windows_Portable' -DestinationPath 'release\InteractiveAtlas_Windows_Portable.zip' -Force"
if errorlevel 1 exit /b 1

echo Portable package created:
echo release\InteractiveAtlas_Windows_Portable.zip
