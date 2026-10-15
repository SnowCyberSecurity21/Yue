; Yue — Inno Setup o'rnatuvchisi.
; Avval: .venv\Scripts\pyinstaller build\yue.spec --noconfirm
;        .venv\Scripts\python tools\third_party.py   (THIRD_PARTY_LICENSES.txt)
; Keyin:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" build\yue.iss
; Natija: dist\Yue-<versiya>-setup.exe — administrator huquqi talab qilinmaydi.
; Jim o'rnatish: /VERYSILENT /SUPPRESSMSGBOXES /NORESTART [/TASKS="desktopicon"]

#define AppName "Yue"
#define AppVersion "0.1.0"
#define AppPublisher "SnowCyberSecurity"
; Windows AppUserModelID — yue/__init__.py dagi APP_ID bilan bir xil
#define AppUserModelID "Yue.DesktopCompanion"

[Setup]
; Nora o'rnatuvchisidan farqli GUID — ikkalasi bitta kompyuterda yonma-yon turadi
AppId={{63C710AD-8B64-4EB7-9FE9-A13462D5E99F}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
DefaultDirName={localappdata}\Programs\Yue
DefaultGroupName=Yue
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
OutputDir=..\dist
OutputBaseFilename=Yue-{#AppVersion}-setup
SetupIconFile=..\assets\packs\yue\yue.ico
UninstallDisplayIcon={app}\Yue.exe
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Faqat Windows 10/11, x64
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

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
uz.ButtonYes=&Ha
uz.ButtonNo=&Yo'q
uz.LicenseLabel3=Litsenziya shartlarini o'qing.
uz.LicenseAccepted=Shartlarga &roziman
uz.LicenseNotAccepted=Shartlarga rozi &emasman
uz.SelectDirLabel3=Yue quyidagi papkaga o'rnatiladi.
uz.SelectTasksLabel2=Qo'shimcha amallarni tanlang:
uz.ReadyLabel1=O'rnatishga tayyor.
uz.FinishedHeadingLabel=O'rnatish tugadi
uz.FinishedLabel=Yue o'rnatildi.
uz.ExitSetupTitle=O'rnatishdan chiqish
uz.ExitSetupMessage=O'rnatish tugamadi. Chiqasizmi?
uz.ConfirmUninstall=Yue o'chirilsinmi?
uz.UninstalledAll=Yue o'chirildi.

[CustomMessages]
uz.DeleteData=Yue ma'lumotlarini (suhbatlar, vazifalar, sozlamalar) ham o'chiraymi?

[Tasks]
; Ikkalasi oldindan belgilangan
Name: "desktopicon"; Description: "Ish stolida yorliq yaratish"; GroupDescription: "Yorliqlar:"
Name: "autostart"; Description: "Windows bilan birga ishga tushirish"; GroupDescription: "Ishga tushish:"

[Files]
Source: "..\dist\Yue\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_LICENSES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\yue.png"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Yue"; Filename: "{app}\Yue.exe"; AppUserModelID: "{#AppUserModelID}"
Name: "{autoprograms}\Yue — qo'llanma"; Filename: "{app}\README.md"
Name: "{autodesktop}\Yue"; Filename: "{app}\Yue.exe"; Parameters: "--toggle"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "Yue"; ValueData: """{app}\Yue.exe"" --autostart"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Yue.exe"; Description: "Yueni hozir ishga tushirish"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM Yue.exe /F"; Flags: runhidden; RunOnceId: "StopYue"

[Code]
procedure StopYue();
var
  Code: Integer;
begin
  { Ishlab turgan Yue yopiladi (faqat Yue.exe — Nora'ga tegilmaydi) }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM Yue.exe /F', '', SW_HIDE,
    ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopYue();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopYue();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { Standart javob — Yo'q. Jim o'chirishda ma'lumotlar qoladi. }
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(CustomMessage('DeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\Yue'), True, True, True);
end;
