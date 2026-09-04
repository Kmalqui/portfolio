#define MyAppName "MeetingScribe"
#define MyAppVersion "0.3.11-beta"
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
OutputBaseFilename=MeetingScribe-0.3.11-beta-One-Click-Windows-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\meetingscribe-icon.ico
UninstallDisplayIcon={app}\MeetingScribe-character-transparent.ico
LicenseFile=LICENSE.txt
InfoBeforeFile=README.md
AppMutex=Local\MeetingScribe.UpdateSafety
CloseApplications=no
RestartApplications=no

[Files]
Source: "dist\MeetingScribe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\meetingscribe-icon.ico"; DestDir: "{app}"; DestName: "MeetingScribe-character-transparent.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\MeetingScribe"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MeetingScribe-character-transparent.ico"; AppUserModelID: "MeetingScribe.MeetingScribe.CharacterTransparent"
Name: "{autodesktop}\MeetingScribe"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MeetingScribe-character-transparent.ico"; AppUserModelID: "MeetingScribe.MeetingScribe.CharacterTransparent"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch MeetingScribe"; Flags: nowait postinstall skipifsilent; Check: DependenciesAreReady
Filename: "{app}\{#MyAppExeName}"; Flags: nowait; Check: IsAppUpdate

[Code]
var
  DependencySetupSucceeded: Boolean;

function UpdateOpenProcess(Access: LongWord; Inherit: Boolean; PID: LongWord): LongWord;
  external 'OpenProcess@kernel32.dll stdcall';
function UpdateWaitForProcess(Handle: LongWord; Milliseconds: LongWord): LongWord;
  external 'WaitForSingleObject@kernel32.dll stdcall';
function UpdateCloseHandle(Handle: LongWord): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';
function UpdateLastError: LongWord;
  external 'GetLastError@kernel32.dll stdcall';

function IsAppUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATEONLY|0}') = '1';
end;

function InitializeSetup: Boolean;
var
  PID: Integer;
  ProcessHandle: LongWord;
  WaitResult: LongWord;
begin
  Result := True;
  if not IsAppUpdate then Exit;
  PID := StrToIntDef(ExpandConstant('{param:UPDATEPID|0}'), 0);
  if (PID <= 0) or not FileExists(AddBackslash(ExpandConstant('{param:UPDATEFROM|}')) + '{#MyAppExeName}') then
  begin
    MsgBox('This update needs an existing MeetingScribe installation. Use the normal installer instead.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  ProcessHandle := UpdateOpenProcess($00100000, False, PID);
  if ProcessHandle = 0 then
  begin
    { Error 87 means the original process has already exited. }
    Result := UpdateLastError = 87;
  end
  else
  begin
    WaitResult := UpdateWaitForProcess(ProcessHandle, 30000);
    UpdateCloseHandle(ProcessHandle);
    Result := WaitResult = 0;
  end;
  if not Result then
    MsgBox('MeetingScribe has not closed safely. The update was cancelled. Close the app and try again.', mbError, MB_OK);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if IsAppUpdate and (CompareText(ExpandFileName(ExpandConstant('{param:UPDATEFROM|}')), ExpandFileName(ExpandConstant('{app}'))) <> 0) then
    Result := 'The update destination does not match the existing app. Please use the normal installer.';
end;

function DependenciesAreReady: Boolean;
begin
  Result := DependencySetupSucceeded and not IsAppUpdate;
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
  { An in-app update replaces the app only. Preserve existing AI models and
    services without downloading or restarting them. }
  if IsAppUpdate then Exit;
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
