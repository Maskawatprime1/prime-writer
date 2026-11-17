; Prime Writer installer (Inno Setup 6). Build with build_installer.ps1.
; Installs per-user (no admin): the app, LanguageTool and a bundled Java runtime.
; Ollama and the AI model are set up on first launch by the app itself.

#define AppName "Prime Writer"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppExe "PrimeWriter.exe"

[Setup]
AppId={{7BD33988-2D93-48D5-9B89-F6E646666E19}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Maskawat Al Sium
AppCopyright=Copyright (c) 2026 Maskawat Al Sium
LicenseFile=..\LICENSE
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Maskawat Al Sium
VersionInfoCopyright=Copyright (c) 2026 Maskawat Al Sium
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
DefaultDirName={localappdata}\Programs\Prime Writer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=PrimeWriter-Setup-{#AppVersion}
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=force

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nPrime Writer checks grammar, rewrites and paraphrases text in any app, completely offline.%n%nOn first launch it will help you install the free AI engine (Ollama) and download the AI model (2.5–5 GB).

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"
Name: "startup"; Description: "&Start Prime Writer when I sign in (runs quietly in the tray)"

[Files]
Source: "..\dist\PrimeWriter\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\tools\LanguageTool-6.6\*"; DestDir: "{app}\tools\LanguageTool-6.6"; Excludes: "tmp"; Flags: recursesubdirs ignoreversion
Source: "..\tools\jre\*"; DestDir: "{app}\tools\jre"; Flags: recursesubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "redist\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "MaskawatAlSium.PrimeWriter"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "MaskawatAlSium.PrimeWriter"; Tasks: desktopicon
Name: "{userstartup}\PrimeWriter"; Filename: "{app}\{#AppExe}"; Parameters: "--background"; Tasks: startup

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft WebView2 runtime…"; Check: NeedsWebView2; Flags: waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{userstartup}\PrimeWriter.lnk"
Type: filesandordirs; Name: "{app}"

[Code]
const
  WebView2Key = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2(Root: Integer; Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not (HasWebView2(HKLM, 'SOFTWARE\WOW6432Node\' + WebView2Key) or
                 HasWebView2(HKLM, 'SOFTWARE\' + WebView2Key) or
                 HasWebView2(HKCU, 'Software\' + WebView2Key));
end;

{ Close Prime Writer and its LanguageTool (bundled Java) so files can be replaced or removed. }
procedure StopRunningCopy();
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -WindowStyle Hidden -Command "Stop-Process -Name PrimeWriter -Force -ErrorAction SilentlyContinue; ' +
    'Get-CimInstance Win32_Process -Filter ''Name=''''java.exe'''''' | Where-Object { $_.CommandLine -like ''*languagetool-server.jar*'' -and $_.ExecutablePath -like ''*\tools\jre\*'' } | ' +
    'ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Start-Sleep -Milliseconds 800"',
    '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningCopy();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopRunningCopy();
  Result := True;
end;
