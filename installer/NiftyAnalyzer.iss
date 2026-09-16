; Nifty Analyzer 2.0 — self-contained per-user Setup (Inno Setup 6)
; SIGNAL-ONLY. Does not place, modify, or cancel broker orders.
; Requires dist\NiftyAnalyzer\NiftyAnalyzer.exe from PyInstaller (build_exe.ps1).

#define MyAppName "Nifty Analyzer"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "vrstoxeze"
#define MyAppExeName "NiftyAnalyzer.exe"
#define MyAppId "{{8E7C2F1A-9B4D-4E6A-A3C1-5D0F2B8A7E91}"
#define MyAppURL "https://github.com/rxhul96/vrstoxeze"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright="SIGNAL-ONLY MODE. Automated trading disabled."
DefaultDirName={localappdata}\NiftyAnalyzer
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\windows
OutputBaseFilename=NiftyAnalyzer-Setup-2.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
SetupIconFile=..\assets\nifty.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupLogging=yes
LicenseFile=LICENSE.txt
InfoBeforeFile=INFO.txt
UsePreviousAppDir=yes
CloseApplications=force
RestartIfNeededByRun=no
ChangesAssociations=no
AllowNoIcons=yes
DirExistsWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=This will install [name/ver] — a signal-only NIFTY 50 Command Desk.%n%nThis software never places broker orders. You always make the final trading decision.
FinishedLabel=Setup has finished installing [name] on your computer. Launch it from the Start Menu. First run uses replay data until you add Kite keys in %APPDATA%\NiftyAnalyzer\.env.

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Dirs]
Name: "{userappdata}\NiftyAnalyzer"; Flags: uninsneveruninstall

[Files]
Source: "..\dist\NiftyAnalyzer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\.env.default"; DestDir: "{userappdata}\NiftyAnalyzer"; DestName: ".env"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "LICENSE.txt"; DestDir: "{app}"; DestName: "SIGNAL-ONLY.txt"; Flags: ignoreversion
Source: "..\WINDOWS_SETUP.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "Signal-only NIFTY Command Desk"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Signal-only NIFTY Command Desk"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Nifty Analyzer now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
