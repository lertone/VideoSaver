; VideoSaver - 安装包脚本（Inno Setup 6）
; 用法：python build_installer.py  或  build_installer.bat
; 特性：许可协议页 / 安装进度 / 桌面快捷方式（可取消）/ 开始菜单 / 卸载程序

#ifndef SrcDir
  #define SrcDir "dist\VideoSaver"
#endif

#define AppName "VideoSaver"
; 版本号可用 build_installer.py --version 1.0.1 从命令行覆盖
#ifndef AppVersion
  #define AppVersion "1.2.9"
#endif
#define AppExe "VideoSaver.exe"
#define AppId "{{8F3C2A16-7B41-4D9E-9C2A-6E5B14A0D3F7}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=VideoSaver
VersionInfoVersion={#AppVersion}.0
VersionInfoDescription={#AppName} 安装程序

; 覆盖安装的真正障碍是旧进程锁着 _internal 里的文件（错误 32）。
; 让 Windows Restart Manager 强制关闭占用文件的程序，且装完不自动重启旧版。
CloseApplications=force
RestartApplications=no

; 用户级安装：不需要管理员权限，不弹 UAC
DefaultDirName={localappdata}\Programs\VideoSaver
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

DisableProgramGroupPage=yes
DisableWelcomePage=no
; DisableDirPage 默认是 auto：检测到旧安装目录就会跳过「选择目标位置」页，
; 升级安装时用户根本没机会改路径。这里强制每次都显示。
DisableDirPage=no
UsePreviousAppDir=yes
; 「准备安装」页再显示一次目标目录，方便用户最后确认
AlwaysShowDirOnReadyPage=yes
LicenseFile=LICENSE.txt
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

OutputDir=installer_out
OutputBaseFilename=VideoSaver-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinese"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "附加任务："; Flags: checkedonce
Name: "quicklaunch"; Description: "创建快速启动栏快捷方式(&Q)"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\使用指引"; Filename: "{app}\{#AppExe}"; Parameters: "--doc"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: quicklaunch

[Run]
Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Parameters: "--fresh"; Description: "立即运行 {#AppName}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\app.ico"

[Code]
{ 覆盖安装前先确认并结束旧进程。Restart Manager 对托盘里的 PyInstaller 窗口程序
  有时检测不到，这里用 tasklist/taskkill 兜底，避免「DeleteFile 错误代码 32」。 }
function OldAppRunning(): Boolean;
var
  RC: Integer;
begin
  Exec('cmd.exe', '/c tasklist /FI "IMAGENAME eq VideoSaver.exe" /NH | find /I "VideoSaver.exe" >nul',
       '', SW_HIDE, ewWaitUntilTerminated, RC);
  Result := (RC = 0);
end;

function InitializeSetup(): Boolean;
var
  RC: Integer;
begin
  Result := True;
  if OldAppRunning() then
  begin
    if MsgBox('检测到「VideoSaver」正在运行。' + #13#10 + #13#10 +
              '覆盖安装需要先关闭它（会中断正在进行的下载）。' + #13#10 +
              '点「是」自动关闭旧程序并继续安装。',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('cmd.exe', '/c taskkill /F /IM VideoSaver.exe >nul 2>&1',
           '', SW_HIDE, ewWaitUntilTerminated, RC);
    end
    else
    begin
      MsgBox('已取消安装。请先右键右下角托盘图标 → 退出，再重新运行本安装包。',
             mbInformation, MB_OK);
      Result := False;
    end;
  end;
end;
