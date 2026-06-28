; ==========================================================================
;  MicroNoise — установщик (Inno Setup 6)
;
;  Компиляция:  installer\build_installer.cmd   (или ISCC.exe MicroNoise.iss)
;  Результат:   installer_output\MicroNoiseSetup.exe
;
;  Что делает установщик:
;    * ставит готовую сборку из dist\MicroNoise в %LOCALAPPDATA%\Programs\MicroNoise;
;    * создаёт ярлык в меню «Пуск» и (по галочке) на рабочем столе;
;    * на странице «Выбор дополнительных задач» даёт галочки для установки
;      программ виртуального аудиокабеля (VB-CABLE / VAC). Если галочка стоит,
;      то В КОНЦЕ установки MicroNoise автоматически запускается установщик
;      соответствующего кабеля (он сам запросит права администратора).
; ==========================================================================

#define AppName "MicroNoise"
#define AppVersion "1.0.0"
#define AppPublisher "sovenov"
#define AppURL "https://github.com/sovenov"
#define AppExeName "MicroNoise.exe"
; Папка с готовой сборкой (onedir). Относительно расположения этого .iss.
#define SourceDir "..\dist\MicroNoise"

[Setup]
AppId={{6F2B1E7A-3C4D-4A9E-B1F2-8D6C0A5E9B34}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={localappdata}\Programs\MicroNoise
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer_output
OutputBaseFilename=MicroNoiseSetup
SetupIconFile=..\noiseclean\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
WizardStyle=modern
Compression=zip
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=yes
; Картинка слева в мастере (по желанию — раскомментируйте, если нужна):
; WizardSmallImageFile=..\noiseclean\assets\brand.png

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
ru.DesktopIconTask=Создать ярлык на рабочем столе
ru.AdditionalShortcuts=Дополнительные ярлыки:
ru.VirtualCableGroup=Виртуальный аудиокабель (нужен для вывода обработанного микрофона):
ru.InstallVBCableTask=Установить VB-CABLE (рекомендуется)
ru.InstallVACTask=Установить Virtual Audio Cable (VAC)
ru.InstallingVBCable=Запуск установки VB-CABLE...
ru.InstallingVAC=Запуск установки Virtual Audio Cable (VAC)...
ru.LaunchAfterInstall=Запустить %1
ru.UninstallShortcut=Удалить %1
en.DesktopIconTask=Create a desktop shortcut
en.AdditionalShortcuts=Additional shortcuts:
en.VirtualCableGroup=Virtual audio cable (needed to output the processed microphone):
en.InstallVBCableTask=Install VB-CABLE (recommended)
en.InstallVACTask=Install Virtual Audio Cable (VAC)
en.InstallingVBCable=Starting VB-CABLE installation...
en.InstallingVAC=Starting Virtual Audio Cable (VAC) installation...
en.LaunchAfterInstall=Launch %1
en.UninstallShortcut=Uninstall %1

[Tasks]
; Ярлык на рабочем столе — отмечен по умолчанию.
Name: "desktopicon"; Description: "{cm:DesktopIconTask}"; GroupDescription: "{cm:AdditionalShortcuts}"
; VB-CABLE — отмечен по умолчанию; VAC — по умолчанию выключен.
Name: "installvbcable"; Description: "{cm:InstallVBCableTask}"; GroupDescription: "{cm:VirtualCableGroup}"
Name: "installvac"; Description: "{cm:InstallVACTask}"; GroupDescription: "{cm:VirtualCableGroup}"; Flags: unchecked

[Files]
; --- Основная программа: вся папка сборки, КРОМЕ установщиков кабелей ---
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "virtual_cables_setup\*"; Flags: ignoreversion recursesubdirs

; --- Установщики виртуальных кабелей ---
; Распаковываются во временную папку ТОЛЬКО при отмеченной галочке и удаляются
; после установки. Копируется вся папка целиком (рядом с .exe лежат нужные
; .inf/.sys/.cat и подпапки x64/x86/...).
Source: "{#SourceDir}\virtual_cables_setup\VB-CABLE_45\*"; DestDir: "{tmp}\vbcable"; Flags: recursesubdirs createallsubdirs deleteafterinstall ignoreversion; Tasks: installvbcable
Source: "{#SourceDir}\virtual_cables_setup\Virtual_Audio_Cable_VAC_4.71_Lite\*"; DestDir: "{tmp}\vac"; Flags: recursesubdirs createallsubdirs deleteafterinstall ignoreversion; Tasks: installvac

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallShortcut,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; В конце установки (если отмечены галочки) запускаем установщики кабелей.
; shellexec — чтобы сработал их собственный запрос прав администратора (UAC);
; waituntilterminated — чтобы установщики кабелей шли по очереди, а не сразу оба.
Filename: "{tmp}\vbcable\VBCABLE_Setup_x64.exe"; WorkingDir: "{tmp}\vbcable"; StatusMsg: "{cm:InstallingVBCable}"; Flags: shellexec waituntilterminated skipifdoesntexist; Tasks: installvbcable
Filename: "{tmp}\vac\setup64.exe"; WorkingDir: "{tmp}\vac"; StatusMsg: "{cm:InstallingVAC}"; Flags: shellexec waituntilterminated skipifdoesntexist; Tasks: installvac
; Предложить запустить программу после завершения мастера.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchAfterInstall,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
