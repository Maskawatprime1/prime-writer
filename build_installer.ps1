# Builds dist\installer\PrimeWriter-Setup-<version>.exe
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File build_installer.ps1 [-Version 1.0.0]
param([string]$Version = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not $Version) { $Version = (& .\.venv\Scripts\python.exe -c "from writer import __version__; print(__version__)").Trim() }
"Building Prime Writer $Version"

# 1. App exe (also builds the React UI and the icon)
& powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
if ($LASTEXITCODE -ne 0) { throw "build_exe.ps1 failed" }

# 2. Bundled Java runtime for LanguageTool (made once from the local JDK with jlink)
if (-not (Test-Path "tools\jre\bin\java.exe")) {
  $jdk = (Get-Command javac -ErrorAction SilentlyContinue).Source
  if (-not $jdk) { throw "A JDK 17+ is needed once to create tools\jre (jlink)" }
  $jdkHome = Split-Path (Split-Path $jdk)
  $mods = "java.base,java.compiler,java.desktop,java.instrument,java.naming,java.scripting,java.sql,jdk.attach,jdk.httpserver,jdk.jdi,jdk.management,jdk.unsupported,java.logging,java.xml,java.management,java.net.http,java.prefs,java.security.jgss,java.xml.crypto,jdk.crypto.ec,jdk.zipfs,jdk.charsets,jdk.localedata"
  & "$jdkHome\bin\jlink.exe" --add-modules $mods --strip-debug --no-man-pages --no-header-files --compress=zip-6 --output tools\jre
}

# 3. Installer
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
  Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)" }
& $iscc /Q "/DAppVersion=$Version" installer\PrimeWriter.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Get-Item "dist\installer\PrimeWriter-Setup-$Version.exe" | ForEach-Object { "Built: $($_.FullName) ({0:N0} MB)" -f ($_.Length / 1MB) }
