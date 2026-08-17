#ifndef AppVersion
  #error AppVersion must be supplied by the build script.
#endif
#ifndef AppVersionTag
  #error AppVersionTag must be supplied by the build script.
#endif

[Setup]
AppName=SINCAL Suite
AppId=SINCAL Suite
AppVersion={#AppVersion}
AppPublisher=Gonzalo Mardones V.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={autopf}\SINCAL
UsePreviousAppDir=no
DefaultGroupName=SINCAL Suite
OutputDir=.\installer_output
OutputBaseFilename=Setup_SINCAL_{#AppVersionTag}
SetupIconFile=logo.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\SINCAL.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "version.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "tutoriales.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "lisps\*"; DestDir: "{app}\lisps"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "mapas\*"; DestDir: "{app}\mapas"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "masters\*"; DestDir: "{app}\masters"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "modulos\*"; DestDir: "{app}\modulos"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "plotstyles\*"; DestDir: "{app}\plotstyles"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "startup\*"; DestDir: "{app}\startup"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "cad-packages\Autodesk\SINCAL.bundle\*"; DestDir: "{commonpf}\Autodesk\ApplicationPlugins\SINCAL.bundle"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pdb"

[Icons]
Name: "{group}\SINCAL Suite"; Filename: "{app}\SINCAL.exe"
Name: "{commondesktop}\SINCAL Suite"; Filename: "{app}\SINCAL.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SINCAL.exe"; Description: "{cm:LaunchProgram,SINCAL Suite}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
const
  LegacyCertThumbprint = 'FBA955A855C5E7C95D7C570E0DB9FB0D98E2721A';
  LegacyRunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';
  LegacyRunValue = 'SINCAL_Suite';
  LegacyMenuDir = 'Directory\shell\SINCAL_Plotear';
  LegacyMenuBg = 'Directory\Background\shell\SINCAL_Plotear';

function NormalizePath(Value: String): String;
begin
  Result := LowerCase(Trim(Value));
  while (Length(Result) > 0) and ((Result[Length(Result)] = '\') or (Result[Length(Result)] = '/')) do
    Delete(Result, Length(Result), 1);
end;

procedure RemovePathEntry(EntryToRemove: String);
var
  CurrentPath, NewPath, Segment: String;
  I: Integer;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    Exit;

  NewPath := '';
  while CurrentPath <> '' do begin
    I := Pos(';', CurrentPath);
    if I > 0 then begin
      Segment := Copy(CurrentPath, 1, I - 1);
      Delete(CurrentPath, 1, I);
    end else begin
      Segment := CurrentPath;
      CurrentPath := '';
    end;

    if NormalizePath(Segment) <> NormalizePath(EntryToRemove) then begin
      if (Segment <> '') then begin
        if NewPath <> '' then
          NewPath := NewPath + ';';
        NewPath := NewPath + Segment;
      end;
    end;
  end;

  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', NewPath);
end;

procedure RemoveLegacyArtifacts;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'), '/c certutil -delstore Root ' + LegacyCertThumbprint, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  RegDeleteValue(HKCU, LegacyRunKey, LegacyRunValue);

  RegDeleteKeyIncludingSubkeys(HKCR, LegacyMenuDir);
  RegDeleteKeyIncludingSubkeys(HKCR, LegacyMenuBg);

  RemovePathEntry(ExpandConstant('{userappdata}\Estandar SINCAL\scripts'));
  RemovePathEntry(ExpandConstant('{userappdata}\Estandar SINCAL'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    RemoveLegacyArtifacts;
end;