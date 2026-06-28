#define AppName "Transcriptor Desktop"
#define AppVersion "1.0.0"
#define AppPublisher "Transcriptor Desktop"
#define AppExeName "TranscriptorDesktop.exe"
#define SourceDir "..\dist\TranscriptorDesktop"

[Setup]
AppId={{8F6E6B5A-DB50-46E4-A50E-2E2D52E10934}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Transcriptor Desktop
DefaultGroupName={#AppName}
DisableProgramGroupPage=no
AllowNoIcons=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer_output
OutputBaseFilename=TranscriptorDesktopSetup
SetupIconFile=..\assets\dino.ico
WizardSmallImageFile=..\assets\dino_transparent_background.png
UninstallDisplayIcon={app}\{#AppExeName}
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
WizardStyle=modern
Compression=zip
SolidCompression=no
DiskSpanning=no
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Messages]
en.SetupAppTitle=Setup
en.SetupWindowTitle=Setup - %1
en.WizardInstalling=Installing
en.InstallingLabel=Please wait while Setup installs [name] on your computer.
en.ExtractingLabel=Extracting files...
en.StatusExtractFiles=Extracting files...
ru.SetupAppTitle=Установка
ru.SetupWindowTitle=Установка - %1
ru.WizardInstalling=Установка
ru.InstallingLabel=Пожалуйста, подождите, пока [name] установится на ваш компьютер.
ru.ExtractingLabel=Распаковка файлов...
ru.StatusExtractFiles=Распаковка файлов...

[CustomMessages]
en.DesktopIconTask=Create a desktop shortcut
en.AdditionalShortcuts=Additional shortcuts:
en.UninstallShortcut=%1 - removal
en.LaunchAfterInstall=Launch %1
en.InstallStatus=Extracting files...
en.InstallEtaCalculating=calculating remaining time...
en.InstallEtaRemaining=estimated time remaining:
en.TimeHourShort=h
en.TimeMinuteShort=min
en.TimeSecondShort=sec
en.DescriptionPageTitle=Program description
en.DescriptionPageSubtitle=Please read this information before installing.
en.DescriptionText1=LLM models for the llm_models_whisper folder are available here:
en.DescriptionText2=https://disk.yandex.ru/d/kO5zXvLNxc8fJQ
en.DescriptionText3=https://cloud.mail.ru/public/d69o/ZGMNhzZmu
en.DescriptionText4=Transcriptor Desktop is a desktop application for live audio transcription.
en.DescriptionText5=The program can transcribe system audio and microphone audio, save the transcript, and work with RU/EN scenarios.
en.DescriptionText6=Whisper models are not included in this installer. The installer creates the required folders and keeps readme files inside them.
en.DescriptionText7=On Windows, system audio is captured through WASAPI loopback. NVIDIA CUDA / CPU use `faster-whisper`; AMD GPU uses external `whisper.cpp` (`whisper-cli`) with `ggml`/`gguf` models.
en.DescriptionText8=False Whisper phrases.
en.DescriptionText9=On silence, noise, or short unclear fragments, Whisper can sometimes hallucinate common phrases from training data. The application selectively suppresses known subtitle boilerplate phrases and subscription prompts case-insensitively.
en.DescriptionText10=For very weak PCs, there is a browser extension that works through the Google Web Speech API:
en.DescriptionText11=https://chromewebstore.google.com/detail/transcriptor/fpgdnlmjjocgihdlfkamjogknmbpaoma?hl=ru
en.DescriptionText12=LLM models for the llm_models_whisper folder are available here:
en.DescriptionText13=open source: sovenov/Transcriptor_desktop
en.DescriptionText14=https://github.com/sovenov/Transcriptor_desktop
en.DescriptionAccepted=I have read this description
en.DescriptionRequired=Please confirm that you have read the description to continue.
ru.DesktopIconTask=Создать ярлык на рабочем столе
ru.AdditionalShortcuts=Дополнительные ярлыки:
ru.UninstallShortcut=%1 - удаление
ru.LaunchAfterInstall=Запустить %1
ru.InstallStatus=Распаковка файлов...
ru.InstallEtaCalculating=расчёт оставшегося времени...
ru.InstallEtaRemaining=осталось примерно:
ru.TimeHourShort=ч.
ru.TimeMinuteShort=мин.
ru.TimeSecondShort=сек.
ru.DescriptionPageTitle=Описание программы
ru.DescriptionPageSubtitle=Пожалуйста, прочитайте эту информацию перед установкой.
ru.DescriptionText1=Модели LLM для папки llm_models_whisper здесь:
ru.DescriptionText2=https://disk.yandex.ru/d/kO5zXvLNxc8fJQ
ru.DescriptionText3=https://cloud.mail.ru/public/d69o/ZGMNhzZmu
ru.DescriptionText4=Transcriptor Desktop - настольное приложение для транскрипции живого аудио.
ru.DescriptionText5=Программа может распознавать системный звук и микрофон, сохранять транскрипт и работать со сценариями RU/EN.
ru.DescriptionText6=Whisper-модели не входят в установщик. Установщик создаёт нужные папки и оставляет readme-файлы внутри них.
ru.DescriptionText7=На Windows системный звук берётся через WASAPI loopback. NVIDIA CUDA / CPU работают через `faster-whisper`, AMD GPU - через внешний `whisper.cpp` (`whisper-cli`) с `ggml`/`gguf`-моделями.
ru.DescriptionText8=Ложные фразы Whisper.
ru.DescriptionText9=На тишине, шуме или коротких неразборчивых фрагментах Whisper иногда галлюцинирует типовые фразы из обучающих данных. Приложение точечно не выводит известные служебные фразы субтитров и призывы подписаться без учета регистра букв.
ru.DescriptionText10=Для совсем слабых ПК есть расширение для браузера, которое работает за счёт google web speach api:
ru.DescriptionText11=https://chromewebstore.google.com/detail/transcriptor/fpgdnlmjjocgihdlfkamjogknmbpaoma?hl=ru
ru.DescriptionText12=Модели LLM для папки llm_models_whisper здесь:
ru.DescriptionText13=open source: sovenov/Transcriptor_desktop
ru.DescriptionText14=https://github.com/sovenov/Transcriptor_desktop
ru.DescriptionAccepted=Я прочитал описание
ru.DescriptionRequired=Подтвердите, что вы прочитали описание, чтобы продолжить.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIconTask}"; GroupDescription: "{cm:AdditionalShortcuts}"; Flags: checkedonce

[Dirs]
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\data\logs"; Permissions: users-modify
Name: "{app}\llm_models_whisper"; Permissions: users-modify
Name: "{app}\llm_models_whisper\faster_whisper"; Permissions: users-modify
Name: "{app}\llm_models_whisper\whisper_cpp"; Permissions: users-modify

[Files]
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\whisper_cpp\*.exe"; DestDir: "{app}\whisper_cpp"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceDir}\whisper_cpp\*.dll"; DestDir: "{app}\whisper_cpp"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceDir}\whisper_cpp\readme_*.txt"; DestDir: "{app}\whisper_cpp"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceDir}\readme_*.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceDir}\llm_models_whisper\readme_*.txt"; DestDir: "{app}\llm_models_whisper"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceDir}\llm_models_whisper\faster_whisper\readme_*.txt"; DestDir: "{app}\llm_models_whisper\faster_whisper"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceDir}\llm_models_whisper\whisper_cpp\readme_*.txt"; DestDir: "{app}\llm_models_whisper\whisper_cpp"; Flags: ignoreversion skipifsourcedoesntexist
Source: "uninstall_transcriptor.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallShortcut,{#AppName}}"; Filename: "{app}\uninstall_transcriptor.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchAfterInstall,{#AppName}}"; Flags: nowait postinstall skipifsilent unchecked

[InstallDelete]
Type: files; Name: "{group}\Удалить {#AppName}.lnk"
Type: files; Name: "{group}\Uninstall {#AppName}.lnk"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\*"
Type: dirifempty; Name: "{app}"

[Code]
function GetTickCount: Longword;
  external 'GetTickCount@kernel32.dll stdcall';

var
  InstallStartTick: Longword;
  LastEtaUpdateTick: Longword;
  DescriptionPage: TWizardPage;
  DescriptionAcceptedCheckBox: TNewCheckBox;

function FormatDuration(TotalSeconds: Integer): String;
var
  Hours: Integer;
  Minutes: Integer;
  Seconds: Integer;
begin
  if TotalSeconds < 0 then
    TotalSeconds := 0;

  Hours := TotalSeconds div 3600;
  Minutes := (TotalSeconds mod 3600) div 60;
  Seconds := TotalSeconds mod 60;

  if Hours > 0 then
    Result := IntToStr(Hours) + ' ' + ExpandConstant('{cm:TimeHourShort}') + ' ' +
      IntToStr(Minutes) + ' ' + ExpandConstant('{cm:TimeMinuteShort}')
  else if Minutes > 0 then
    Result := IntToStr(Minutes) + ' ' + ExpandConstant('{cm:TimeMinuteShort}') + ' ' +
      IntToStr(Seconds) + ' ' + ExpandConstant('{cm:TimeSecondShort}')
  else
    Result := IntToStr(Seconds) + ' ' + ExpandConstant('{cm:TimeSecondShort}');
end;

procedure UpdateInstallStatus(EtaText: String);
begin
  WizardForm.StatusLabel.Caption := ExpandConstant('{cm:InstallStatus}') + ' ' + EtaText;
end;

procedure InitializeWizard;
var
  DescriptionMemo: TNewMemo;
begin
  InstallStartTick := 0;
  LastEtaUpdateTick := 0;

  DescriptionPage := CreateCustomPage(
    wpWelcome,
    ExpandConstant('{cm:DescriptionPageTitle}'),
    ExpandConstant('{cm:DescriptionPageSubtitle}')
  );

  DescriptionMemo := TNewMemo.Create(DescriptionPage);
  DescriptionMemo.Left := 0;
  DescriptionMemo.Top := 0;
  DescriptionMemo.Width := DescriptionPage.SurfaceWidth;
  DescriptionMemo.Height := DescriptionPage.SurfaceHeight - ScaleY(42);
  DescriptionMemo.ScrollBars := ssVertical;
  DescriptionMemo.ReadOnly := True;
  DescriptionMemo.Text :=
    ExpandConstant('{cm:DescriptionText1}') + #13#10#13#10 +
    ExpandConstant('{cm:DescriptionText2}') + #13#10 +
    ExpandConstant('{cm:DescriptionText3}') + #13#10#13#10 +
    ExpandConstant('{cm:DescriptionText4}') + #13#10 +
    ExpandConstant('{cm:DescriptionText5}') + #13#10 +
    ExpandConstant('{cm:DescriptionText6}') + #13#10#13#10 +
    ExpandConstant('{cm:DescriptionText7}') + #13#10#13#10 +
    ExpandConstant('{cm:DescriptionText8}') + #13#10 +
    ExpandConstant('{cm:DescriptionText9}') + #13#10#13#10 +
    ExpandConstant('{cm:DescriptionText10}') + #13#10 +
    ExpandConstant('{cm:DescriptionText11}') + #13#10#13#10 +
    ExpandConstant('{cm:DescriptionText12}') + #13#10 +
    ExpandConstant('{cm:DescriptionText2}') + #13#10 +
    ExpandConstant('{cm:DescriptionText3}') + #13#10#13#10 +
    ExpandConstant('{cm:DescriptionText13}') + #13#10 +
    ExpandConstant('{cm:DescriptionText14}');
  DescriptionMemo.Parent := DescriptionPage.Surface;

  DescriptionAcceptedCheckBox := TNewCheckBox.Create(DescriptionPage);
  DescriptionAcceptedCheckBox.Left := 0;
  DescriptionAcceptedCheckBox.Top := DescriptionMemo.Top + DescriptionMemo.Height + ScaleY(12);
  DescriptionAcceptedCheckBox.Width := DescriptionPage.SurfaceWidth;
  DescriptionAcceptedCheckBox.Height := ScaleY(24);
  DescriptionAcceptedCheckBox.Caption := ExpandConstant('{cm:DescriptionAccepted}');
  DescriptionAcceptedCheckBox.Checked := False;
  DescriptionAcceptedCheckBox.Parent := DescriptionPage.Surface;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = DescriptionPage.ID then
  begin
    if not DescriptionAcceptedCheckBox.Checked then
    begin
      MsgBox(ExpandConstant('{cm:DescriptionRequired}'), mbInformation, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    InstallStartTick := GetTickCount;
    LastEtaUpdateTick := 0;
    UpdateInstallStatus(ExpandConstant('{cm:InstallEtaCalculating}'));
  end;
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
var
  NowTick: Longword;
  ElapsedSeconds: Integer;
  RemainingSeconds: Integer;
begin
  if InstallStartTick = 0 then
    InstallStartTick := GetTickCount;

  NowTick := GetTickCount;
  if (LastEtaUpdateTick <> 0) and (NowTick - LastEtaUpdateTick < 1000) then
    Exit;

  LastEtaUpdateTick := NowTick;
  ElapsedSeconds := (NowTick - InstallStartTick) div 1000;

  if (CurProgress <= 0) or (MaxProgress <= 0) or (ElapsedSeconds < 3) then
  begin
    UpdateInstallStatus(ExpandConstant('{cm:InstallEtaCalculating}'));
    Exit;
  end;

  if CurProgress >= MaxProgress then
    RemainingSeconds := 0
  else
    RemainingSeconds := (ElapsedSeconds * (MaxProgress - CurProgress)) div CurProgress;

  UpdateInstallStatus(ExpandConstant('{cm:InstallEtaRemaining}') + ' ' + FormatDuration(RemainingSeconds));
end;
