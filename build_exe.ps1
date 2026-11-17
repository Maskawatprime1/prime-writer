# Builds dist\PrimeWriter\PrimeWriter.exe
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Close a running copy so its files can be replaced.
Get-Process PrimeWriter -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

# Build the React UI (frontend/) into writer/static/app
Push-Location frontend
if (-not (Test-Path node_modules)) { npm install --no-audit --no-fund }
npx vite build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Frontend build failed" }
Pop-Location

New-Item -ItemType Directory -Force build | Out-Null
& .\.venv\Scripts\python.exe -c "from writer.brand import save_ico; save_ico(r'build\icon.ico')"
& .\.venv\Scripts\python.exe scripts\version_info.py
& .\.venv\Scripts\python.exe scripts\gen_notices.py

& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed `
  --name PrimeWriter `
  --icon "$PSScriptRoot\build\icon.ico" `
  --version-file "$PSScriptRoot\build\version_info.txt" `
  --add-data "$PSScriptRoot\LICENSE;." `
  --add-data "$PSScriptRoot\THIRD-PARTY-NOTICES.md;." `
  --distpath dist --workpath build --specpath build `
  --paths . `
  --add-data "$PSScriptRoot\writer\static;writer\static" `
  --collect-submodules uvicorn `
  --hidden-import pystray._win32 `
  --hidden-import writer.overlay `
  --collect-submodules comtypes `
  --exclude-module faster_whisper --exclude-module ctranslate2 --exclude-module av `
  --exclude-module onnxruntime --exclude-module tkinter `
  primewriter.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "Built: $PSScriptRoot\dist\PrimeWriter\PrimeWriter.exe"
