#define MyAppName "MeetingScribe"
#define MyAppVersion "0.3.6-beta"
#define MyAppPublisher "MeetingScribe Community Beta"
#define MyAppExeName "MeetingScribe.exe"

[Setup]
AppId={{72B7E1AC-8849-45D0-8FF2-8DDB1A90648B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=installer-output
OutputBaseFilename=MeetingScribe-0.3.6-beta-One-Click-Windows-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\meetingscribe-icon.ico
UninstallDisplayIcon={app}\MeetingScribe-0.3.ico
LicenseFile=LICENSE.txt
InfoBeforeFile=README.md

[Files]
Source: "dist\MeetingScribe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\meetingscribe-icon.ico"; DestDir: "{app}"; DestName: "MeetingScribe-0.3.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\MeetingScribe"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MeetingScribe-0.3.ico"; AppUserModelID: "MeetingScribe.MeetingScribe.0.3"
Name: "{autodesktop}\MeetingScribe"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MeetingScribe-0.3.ico"; AppUserModelID: "MeetingScribe.MeetingScribe.0.3"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch MeetingScribe"; Flags: nowait postinstall skipifsilent; Check: DependenciesAreReady

[Code]
var
  DependencySetupSucceeded: Boolean;

function DependenciesAreReady: Boolean;
begin
  Result := DependencySetupSucceeded;
end;

procedure DependencyError(const Details: String);
begin
  DependencySetupSucceeded := False;
  MsgBox(
    'MeetingScribe was installed, but automatic local-AI setup did not finish.' + #13#10 + #13#10 +
    Details + #13#10 + #13#10 +
    'Keep the installer and run it again while connected to the internet. The README also contains manual recovery steps.',
    mbError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  OllamaExe: String;
  OllamaInstaller: String;
  ResultCode: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;

  DependencySetupSucceeded := True;
  OllamaExe := ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe');

  if not FileExists(OllamaExe) then
  begin
    WizardForm.StatusLabel.Caption := 'Downloading Ollama from ollama.com...';
    DownloadTemporaryFile(
      'https://ollama.com/download/OllamaSetup.exe',
      'OllamaSetup.exe', '', nil);
    OllamaInstaller := ExpandConstant('{tmp}\OllamaSetup.exe');

    WizardForm.StatusLabel.Caption := 'Installing Ollama...';
    if not Exec(OllamaInstaller,
      '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
    begin
      DependencyError('Ollama could not be installed.');
      Exit;
    end;
  end;

  if not FileExists(OllamaExe) then
  begin
    DependencyError('The Ollama program could not be found after installation.');
    Exit;
  end;

  { Start the local service if the Ollama tray application has not done so. }
  Exec(OllamaExe, 'serve', '', SW_HIDE, ewNoWait, ResultCode);
  Sleep(4000);

  WizardForm.StatusLabel.Caption :=
    'Downloading the local note-writing model. Do not close the download window...';
  if not Exec(OllamaExe, 'pull qwen3:4b', '', SW_SHOW,
    ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    DependencyError('The qwen3:4b local AI model could not be downloaded.');
    Exit;
  end;

  WizardForm.StatusLabel.Caption :=
    'Downloading the local transcription model. This may take several minutes...';
  if not Exec(ExpandConstant('{app}\{#MyAppExeName}'), '--preload-whisper',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    DependencyError('The Whisper transcription model could not be downloaded.');
    Exit;
  end;

  WizardForm.StatusLabel.Caption := 'MeetingScribe is ready.';
end;
