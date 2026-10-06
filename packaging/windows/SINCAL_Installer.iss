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
#ifndef ReleaseOutputDir
  #error ReleaseOutputDir must be supplied by the build script.
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
OutputDir={#ReleaseOutputDir}
OutputBaseFilename=Setup_SINCAL_{#AppVersionTag}
SetupIconFile=..\..\assets\icons\logo.ico
Compression=lzma
SolidCompression=yes
ArchiveExtraction=full
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=yes

; Classic Explorer integration; the DLL only forwards the selected DWG list.
#if defined(DesktopWebSetup) && DesktopWebSetup == "1"
[Registry]
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL"; ValueType: string; ValueName: "MUIVerb"; ValueData: "SINCAL Suite"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL"; ValueType: string; ValueName: "SubCommands"; ValueData: ""
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\SINCAL.exe,0"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\01"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Configurar A1"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\01"; ValueType: string; ValueName: "ExplorerCommandHandler"; ValueData: "{{8549E221-34D5-4E21-937C-22D8F0300101}"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\01"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300101}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300101}\InprocServer32"; ValueType: string; ValueData: "{app}\SincalShell.dll"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300101}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Apartment"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\02"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Plotear a PDF"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\02"; ValueType: string; ValueName: "ExplorerCommandHandler"; ValueData: "{{8549E221-34D5-4E21-937C-22D8F0300102}"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\02"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300102}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300102}\InprocServer32"; ValueType: string; ValueData: "{app}\SincalShell.dll"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300102}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Apartment"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\03"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Configurar A1 y plotear"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\03"; ValueType: string; ValueName: "ExplorerCommandHandler"; ValueData: "{{8549E221-34D5-4E21-937C-22D8F0300103}"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\03"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300103}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300103}\InprocServer32"; ValueType: string; ValueData: "{app}\SincalShell.dll"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300103}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Apartment"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\04"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Encuadrar y guardar"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\04"; ValueType: string; ValueName: "ExplorerCommandHandler"; ValueData: "{{8549E221-34D5-4E21-937C-22D8F0300104}"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\04"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300104}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300104}\InprocServer32"; ValueType: string; ValueData: "{app}\SincalShell.dll"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300104}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Apartment"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\05"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Limpiar y guardar"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\05"; ValueType: string; ValueName: "ExplorerCommandHandler"; ValueData: "{{8549E221-34D5-4E21-937C-22D8F0300105}"
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.dwg\shell\SINCAL\shell\05"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300105}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300105}\InprocServer32"; ValueType: string; ValueData: "{app}\SincalShell.dll"
Root: HKLM; Subkey: "Software\Classes\CLSID\{{8549E221-34D5-4E21-937C-22D8F0300105}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Apartment"

#endif
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppPayloadUrl}"; DestDir: "{app}"; DestName: "SINCAL_App_{#AppVersionTag}.zip"; ExternalSize: {#AppPayloadSize}; Hash: "{#AppPayloadHash}"; Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion
Source: "{#PluginPayloadUrl}"; DestDir: "{commonpf}\Autodesk\ApplicationPlugins\SINCAL.bundle"; DestName: "SINCAL_AutoCAD_{#AppVersionTag}.zip"; ExternalSize: {#PluginPayloadSize}; Hash: "{#PluginPayloadHash}"; Flags: external download extractarchive recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
Type: filesandordirs; Name: "{app}\ocr_runtime"
Type: filesandordirs; Name: "{app}\lisps"
Type: filesandordirs; Name: "{app}\mapas"
Type: filesandordirs; Name: "{app}\masters"
Type: filesandordirs; Name: "{app}\modulos"
Type: filesandordirs; Name: "{app}\plotstyles"
Type: filesandordirs; Name: "{app}\scripts"
Type: filesandordirs; Name: "{app}\startup"
Type: filesandordirs; Name: "{app}\assets"

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

  { This is an active CAD resource directory, not a legacy PATH entry. }
  RemovePathEntry(ExpandConstant('{userappdata}\Estandar SINCAL'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  CurrentPath, ScriptsPath: String;
begin
  if CurStep = ssInstall then
    RemoveLegacyArtifacts;
  if CurStep = ssPostInstall then begin
    ScriptsPath := ExpandConstant('{app}\scripts');
    RemovePathEntry(ScriptsPath);
    RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath);
    if CurrentPath <> '' then
      ScriptsPath := ScriptsPath + ';' + CurrentPath;
    if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', ScriptsPath) then
      Log('No se pudo registrar scripts en el PATH del usuario.');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemovePathEntry(ExpandConstant('{app}\scripts'));
end;
