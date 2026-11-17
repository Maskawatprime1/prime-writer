# One-time setup for building Prime Writer from source on Windows.
# Needs: Python 3.13 + uv, Node.js 20+, a JDK 17+ (for jlink), Inno Setup 6 (for the installer).
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File scripts\setup_dev.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

# Python environment
uv venv .venv --python 3.13
uv pip install -p .venv -r requirements.txt

# UI dependencies
Push-Location frontend; npm install --no-audit --no-fund; Pop-Location

# LanguageTool 6.6 (LGPL) into tools\
New-Item -ItemType Directory -Force tools | Out-Null
if (-not (Test-Path "tools\LanguageTool-6.6\languagetool-server.jar")) {
  curl.exe -L --fail -o tools\LanguageTool-6.6.zip https://languagetool.org/download/LanguageTool-6.6.zip
  Expand-Archive -Force tools\LanguageTool-6.6.zip tools
  Remove-Item tools\LanguageTool-6.6.zip
}

# Microsoft WebView2 bootstrapper (bundled by the installer for PCs that lack WebView2)
New-Item -ItemType Directory -Force installer\redist | Out-Null
if (-not (Test-Path "installer\redist\MicrosoftEdgeWebview2Setup.exe")) {
  curl.exe -L --fail -o installer\redist\MicrosoftEdgeWebview2Setup.exe "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
}

"Ready. Build the installer with:  powershell -ExecutionPolicy Bypass -File build_installer.ps1"
