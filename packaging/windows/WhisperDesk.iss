; Per-user installer. GPU runtime and model downloads are locked at build time.
[Setup]
AppId={{EF14A980-E239-414E-A6F4-ABAB4AF008F2}
AppName=WhisperDesk
AppVersion={#ReleaseVersion}
UninstallDisplayName=WhisperDesk
AppPublisher=DotSam
AppPublisherURL={#ProjectUrl}
AppSupportURL={#SupportUrl}
AppUpdatesURL={#ProjectUrl}/releases
DefaultDirName={localappdata}\Programs\WhisperDesk
DefaultGroupName=Whisper Desk
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.22000
OutputDir={#OutputDir}
OutputBaseFilename={#InstallerBaseFilename}
SetupIconFile=..\..\src\whisper_desk\assets\app.ico
UninstallDisplayIcon={app}\WhisperDesk.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern dynamic windows11
WizardSizePercent=110
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "{#AppSource}\*"; DestDir: "{tmp}\payload"; Flags: dontcopy recursesubdirs createallsubdirs
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Whisper Desk"; Filename: "{app}\WhisperDesk.exe"; AppUserModelID: "WhisperDesk.Desktop"

[Run]
Filename: "{app}\WhisperDesk.exe"; Description: "Open Whisper Desk"; Flags: nowait postinstall skipifsilent; Check: SetupVerified

[Code]
var
  DownloadPage: TDownloadWizardPage;
  CheckPage: TOutputProgressWizardPage;
  GpuPage: TInputOptionWizardPage;
  CacheDir, DataDir, Helper: String;
  ProbeCode: Integer;
  Verified, DependenciesReady, Checking: Boolean;

function SetupVerified: Boolean;
begin
  Result := Verified;
end;

function HelperRun(Command, OutputName: String; Gpu: Boolean): Integer;
var
  Parameters: String;
begin
  Parameters := '--setup-' + Command + ' --setup-root "' + DataDir +
    '" --setup-cache "' + CacheDir + '" --setup-output "' + DataDir + '\' + OutputName + '"';
  if Gpu then Parameters := Parameters + ' --require-cuda';
  Checking := True;
  try
    if not Exec(Helper, Parameters, '', SW_HIDE, ewWaitUntilTerminated, Result) then
      RaiseException('Could not start the setup checker.');
  finally
    Checking := False;
  end;
end;

procedure DownloadLocked(DisplayName, URL, Filename, Hash: String);
var
  Cached: String;
begin
  Cached := CacheDir + '\' + Filename;
  if FileExists(Cached) then begin
    if CompareText(GetSHA256OfFile(Cached), Hash) = 0 then exit;
    DeleteFile(Cached);
  end;
  DownloadPage.Clear;
  DownloadPage.SetText('Downloading ' + DisplayName, 'Your recordings stay private. These files enable offline transcription.');
  DownloadPage.Add(URL, DisplayName, Hash);
  DownloadPage.Show;
  try
    DownloadPage.Download;
    if not CopyFile(ExpandConstant('{tmp}\') + DisplayName, Cached, False) then
      RaiseException('Could not save the verified download. Check free disk space.');
    DeleteFile(ExpandConstant('{tmp}\') + DisplayName);
  finally
    DownloadPage.Hide;
  end;
end;

#include ManifestInclude

procedure InitializeWizard;
begin
  DataDir := ExpandConstant('{localappdata}\WhisperDesk');
  CacheDir := DataDir + '\setup-cache';
  ForceDirectories(CacheDir);
  Helper := ExpandConstant('{tmp}\payload\WhisperDesk.exe');
  CheckPage := CreateOutputProgressPage('Checking your computer', 'Preparing private, offline transcription.');
  CheckPage.Show;
  try
    ExtractTemporaryFiles('{tmp}\payload\*');
    ProbeCode := HelperRun('probe', 'setup-probe.json', False);
  finally
    CheckPage.Hide;
  end;
  GpuPage := CreateInputOptionPage(wpSelectDir, 'Transcription acceleration',
    'Whisper Turbo runs locally on your computer.',
    'Setup downloads the model (about 1.6 GB). GPU mode also downloads native NVIDIA libraries (about 1.8 GB). A compatible NVIDIA driver is required; Python and the CUDA Toolkit are not.', False, False);
  GpuPage.Add('Enable NVIDIA GPU acceleration (recommended for live transcription)');
  GpuPage.Values[0] := ProbeCode = 0;
  if ExpandConstant('{param:CPU|0}') = '1' then GpuPage.Values[0] := False;
  GpuPage.CheckListBox.ItemEnabled[0] := ProbeCode <> 10;
  if ProbeCode = 11 then
    GpuPage.SubCaptionLabel.Caption := 'NVIDIA driver unavailable. Update it at nvidia.com/drivers, or continue in slower CPU mode.';
  DownloadPage := CreateDownloadPage('Downloading transcription files', 'This is a one-time download.', nil);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
  Verified := False;
  DependenciesReady := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if CurPageID = GpuPage.ID then DependenciesReady := False;
  Result := True;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + NewLine + 'Private offline transcription:' + NewLine + Space + 'Whisper Turbo model downloaded and verified during setup.';
  if GpuPage.Values[0] then
    Result := Result + NewLine + Space + 'NVIDIA GPU mode: about 3.44 GB of downloads in total.'
  else
    Result := Result + NewLine + Space + 'CPU mode: about 1.62 GB of downloads; transcription is slower.';
  Result := Result + NewLine + Space + 'No Python, CUDA Toolkit or cuDNN installation required.';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  FreeMB, TotalMB: Cardinal;
  RequiredMB: Cardinal;
  Code: Integer;
begin
  Result := '';
  if DependenciesReady then exit;
  try
    DeleteFile(DataDir + '\setup.cancel');
    RequiredMB := ModelSpaceMB;
    if GpuPage.Values[0] then RequiredMB := RequiredMB + GpuSpaceMB;
    if not GetSpaceOnDisk(DataDir, True, FreeMB, TotalMB) or (FreeMB < RequiredMB) then
      RaiseException(Format('Setup needs approximately %d MB of free space for downloads and staging.', [RequiredMB]));
    DownloadModelDependencies;
    if GpuPage.Values[0] then DownloadGpuDependencies;
    CheckPage.SetText('Installing transcription files', 'Checking downloaded files and preparing the model. This may take a few minutes.');
    CheckPage.Show;
    try
      Code := HelperRun('stage', 'setup-stage.json', GpuPage.Values[0]);
      if Code <> 0 then RaiseException('Could not prepare the transcription files. Details: ' + DataDir + '\setup-stage.json');
      CheckPage.SetText('Checking transcription', 'Loading Whisper Turbo and running actual inference.');
      Code := HelperRun('verify', 'setup-verification.json', GpuPage.Values[0]);
      if Code <> 0 then RaiseException('Transcription check failed. Update your NVIDIA driver or select CPU mode. Details: ' + DataDir + '\setup-verification.json');
    finally
      CheckPage.Hide;
    end;
    DependenciesReady := True;
  except
    Result := GetExceptionMessage + #13#10 + 'You can retry. Completed, verified downloads are retained.';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
begin
  if CurStep = ssPostInstall then begin
    Helper := ExpandConstant('{app}\WhisperDesk.exe');
    CheckPage.SetText('Checking installed application', 'Confirming the installed app can transcribe offline.');
    CheckPage.Show;
    try
      Code := HelperRun('verify', 'setup-verification.json', GpuPage.Values[0]);
      if Code <> 0 then RaiseException('Installed application verification failed. Run Setup again to repair it.');
      if GpuPage.Values[0] then
        Verified := SaveStringToFile(DataDir + '\installed.json', '{"schema":1,"installer":"{#ReleaseVersion}","gpu_enabled":true}', False)
      else
        Verified := SaveStringToFile(DataDir + '\installed.json', '{"schema":1,"installer":"{#ReleaseVersion}","gpu_enabled":false}', False);
      if not Verified then
        RaiseException('Could not save the installation marker.');
      Verified := True;
    finally
      CheckPage.Hide;
    end;
  end;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if Checking then begin
    SaveStringToFile(DataDir + '\setup.cancel', 'cancel', False);
    Cancel := False;
    Confirm := False;
    CheckPage.SetText('Cancelling setup', 'Waiting for the current verification step to finish safely.');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    if (not UninstallSilent) and (MsgBox('Also remove downloaded models, GPU libraries, setup cache and logs? Keeping them makes reinstalling faster.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      DelTree(ExpandConstant('{localappdata}\WhisperDesk'), True, True, True);
  end;
end;
