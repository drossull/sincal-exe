#ifndef AppVersion
  #error AppVersion must be supplied by the build script.
#endif
#ifndef AppVersionTag
  #error AppVersionTag must be supplied by the build script.
#endif
#ifndef AppPayloadUrl
  #error AppPayloadUrl must be supplied by the build script.
#endif
#ifndef AppPayloadHash
  #error AppPayloadHash must be supplied by the build script.
#endif
#ifndef AppPayloadSize
  #error AppPayloadSize must be supplied by the build script.
#endif
#ifndef PluginPayloadUrl
  #error PluginPayloadUrl must be supplied by the build script.
#endif
#ifndef PluginPayloadHash
  #error PluginPayloadHash must be supplied by the build script.
#endif
#ifndef PluginPayloadSize
  #error PluginPayloadSize must be supplied by the build script.
#endif

[Setup]
AppName=SINCAL Suite
AppId=SINCAL Suite
AppVersion={#AppVersion}
AppPublisher=Gonzalo Mardones V.
AppUpdatesURL=https://github.com/drossull/sincal-updates/releases
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={autopf}\SINCAL
UsePreviousAppDir=yes
DefaultGroupName=SINCAL Suite
OutputDir=.\installer_output
OutputBaseFilename=Setup_SINCAL_{#AppVersionTag}
SetupIconFile=logo.ico
Compression=lzma
SolidCompression=yes
ArchiveExtraction=full
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppPayloadUrl}"; DestDir: "{app}"; DestName: "SINCAL_App_{#AppVersionTag}.zip"; ExternalSize: {#AppPayloadSize}; Hash: "{#AppPayloadHash}"; Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "{#PluginPayloadUrl}"; DestDir: "{commonpf}\Autodesk\ApplicationPlugins\SINCAL.bundle"; DestName: "SINCAL_AutoCAD_{#AppVersionTag}.zip"; ExternalSize: {#PluginPayloadSize}; Hash: "{#PluginPayloadHash}"; Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
Type: filesandordirs; Name: "{app}\lisps"
Type: filesandordirs; Name: "{app}\mapas"
Type: filesandordirs; Name: "{app}\masters"
Type: filesandordirs; Name: "{app}\modulos"
Type: filesandordirs; Name: "{app}\plotstyles"
Type: filesandordirs; Name: "{app}\scripts"
Type: filesandordirs; Name: "{app}\startup"

[Icons]
Name: "{group}\SINCAL Suite"; Filename: "{app}\SINCAL.exe"
Name: "{commondesktop}\SINCAL Suite"; Filename: "{app}\SINCAL.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SINCAL.exe"; Description: "{cm:LaunchProgram,SINCAL Suite}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
const
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
begin
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
