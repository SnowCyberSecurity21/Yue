; Yue — Inno Setup o'rnatuvchisi (ixtiyoriy).
; Avval: .venv\Scripts\pyinstaller build\yue.spec --noconfirm
; Keyin:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" build\yue.iss
;         (yoki "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" — qayerga o'rnatilganiga qarab)
; Natija: dist\Yue-0.1.0-setup.exe — administrator huquqi talab qilinmaydi.

#define AppName "Yue"
#define AppVersion "0.1.0"
; Windows AppUserModelID — yue/__init__.py dagi APP_ID bilan bir xil
#define AppUserModelID "Yue.DesktopCompanion"

[Setup]
; Nora o'rnatuvchisidan farqli GUID — ikkalasi bitta kompyuterda yonma-yon turadi
AppId={{63C710AD-8B64-4EB7-9FE9-A13462D5E99F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Yue
DefaultDirName={localappdata}\Programs\Yue
DefaultGroupName=Yue
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
OutputDir=..\dist
OutputBaseFilename=Yue-{#AppVersion}-setup
SetupIconFile=..\assets\packs\yue\yue.ico
UninstallDisplayIcon={app}\Yue.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
; Inno Setup'da rasmiy o'zbekcha tarjima yo'q — asosiy matnlar pastda o'zbekcha berilgan.
Name: "uz"; MessagesFile: "compiler:Default.isl"

[Messages]
uz.SetupAppTitle=O'rnatish
uz.SetupWindowTitle=O'rnatish — %1
uz.WelcomeLabel1=[name] o'rnatuvchisiga xush kelibsiz
uz.WelcomeLabel2=Kompyuteringizga [name/ver] o'rnatiladi.%n%nDavom etishdan oldin boshqa dasturlarni yopish tavsiya etiladi.
uz.ButtonNext=&Keyingisi >
uz.ButtonBack=< &Orqaga
uz.ButtonCancel=Bekor qilish
uz.ButtonInstall=&O'rnatish
uz.ButtonFinish=&Tayyor
uz.SelectDirLabel3=Yue quyidagi papkaga o'rnatiladi.
uz.SelectTasksLabel2=Qo'shimcha amallarni tanlang:
uz.ReadyLabel1=O'rnatishga tayyor.
uz.FinishedHeadingLabel=O'rnatish tugadi
uz.FinishedLabel=Yue o'rnatildi.
uz.ExitSetupTitle=O'rnatishdan chiqish
uz.ExitSetupMessage=O'rnatish tugamadi. Chiqasizmi?
uz.ConfirmUninstall=Yue o'chirilsinmi? (Xotira va sozlamalar %APPDATA%\Yue papkasida qoladi.)
uz.UninstalledAll=Yue o'chirildi.

[Tasks]
Name: "desktopicon"; Description: "Ish stolida yorliq yaratish"; GroupDescription: "Yorliqlar:"
Name: "autostart"; Description: "Windows bilan birga ishga tushirish"; GroupDescription: "Ishga tushish:"

[Files]
Source: "..\dist\Yue\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Yue"; Filename: "{app}\Yue.exe"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\Yue"; Filename: "{app}\Yue.exe"; Parameters: "--toggle"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "Yue"; ValueData: """{app}\Yue.exe"" --autostart"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Yue.exe"; Description: "Yueni hozir ishga tushirish"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM Yue.exe /F"; Flags: runhidden; RunOnceId: "StopYue"
