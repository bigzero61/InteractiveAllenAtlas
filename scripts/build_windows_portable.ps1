$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (!(Test-Path ".venv")) {
    & ".\scripts\install_windows.bat"
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pyinstaller

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

& ".\.venv\Scripts\pyinstaller.exe" --clean --noconfirm "InteractiveAtlas.spec"

New-Item -ItemType Directory -Force "release" | Out-Null
if (Test-Path "release\InteractiveAtlas_Windows_Portable") {
    Remove-Item "release\InteractiveAtlas_Windows_Portable" -Recurse -Force
}
Copy-Item "dist\InteractiveAtlas" "release\InteractiveAtlas_Windows_Portable" -Recurse
Copy-Item "README.md" "release\InteractiveAtlas_Windows_Portable\README.md" -Force

Compress-Archive -Path "release\InteractiveAtlas_Windows_Portable" -DestinationPath "release\InteractiveAtlas_Windows_Portable.zip" -Force
Write-Host "Portable package created: release\InteractiveAtlas_Windows_Portable.zip"
