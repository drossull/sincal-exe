#ifndef ModuleVersion
  #error ModuleVersion must be supplied by the build script.
#endif
#ifndef ModuleStageDir
  #error ModuleStageDir must be supplied by the build script.
#endif
#ifndef ModuleOutputDir
  #error ModuleOutputDir must be supplied by the build script.
#endif

[Setup]
AppId=SINCAL Pasarela BIM
AppName=SINCAL · Pasarela BIM
AppVersion={#ModuleVersion}
AppPublisher=Gonzalo Mardones V.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={localappdata}\SINCAL\modules\pasarela-bim
DisableDirPage=yes
UsePreviousAppDir=no
DefaultGroupName=SINCAL Suite
DisableProgramGroupPage=yes
OutputDir={#ModuleOutputDir}
OutputBaseFilename=Setup_SINCAL_Pasarela_v{#ModuleVersion}
SetupIconFile=..\..\assets\icons\logo.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
CloseApplications=yes
CloseApplicationsFilter=SINCAL-Pasarela.exe
RestartApplications=no
UninstallDisplayIcon={app}\SINCAL-Pasarela.exe

[Files]
Source: "{#ModuleStageDir}\SINCAL-Pasarela.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ModuleStageDir}\module.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\SINCAL Suite\Pasarela BIM"; Filename: "{app}\SINCAL-Pasarela.exe"; Parameters: "--port 0"

; Los proyectos y resultados están fuera de la carpeta del módulo. Desinstalar
; este complemento no elimina datos, FreeCAD ni la aplicación principal.
[Run]
Filename: "{app}\SINCAL-Pasarela.exe"; Parameters: "--port 0"; Description: "Abrir Pasarela BIM"; Flags: nowait postinstall skipifsilent unchecked
