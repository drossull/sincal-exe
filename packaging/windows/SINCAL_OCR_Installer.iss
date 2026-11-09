#ifndef ModuleVersion
  #error ModuleVersion must be supplied by the build script.
#endif
#ifndef ModuleStageDir
  #error ModuleStageDir must be supplied by the build script.
#endif
#ifndef ModuleOutputDir
  #error ModuleOutputDir must be supplied by the build script.
#endif
#ifndef OcrRuntimeDir
  #error OcrRuntimeDir must be supplied by the build script.
#endif

[Setup]
AppId=SINCAL Prospecciones OCR
AppName=SINCAL · OCR de Prospecciones
AppVersion={#ModuleVersion}
AppPublisher=Gonzalo Mardones V.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={localappdata}\SINCAL\modules\prospecciones-ocr
DisableDirPage=yes
UsePreviousAppDir=no
DisableProgramGroupPage=yes
OutputDir={#ModuleOutputDir}
OutputBaseFilename=Setup_SINCAL_OCR_v{#ModuleVersion}
SetupIconFile=..\..\assets\icons\logo.ico
Compression=lzma2/fast
SolidCompression=yes
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#ModuleStageDir}\module.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#OcrRuntimeDir}\*"; DestDir: "{app}\ocr_runtime"; Excludes: "__pycache__\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; This installer owns only its engine. Remove obsolete dependencies on upgrade.
Type: filesandordirs; Name: "{app}\ocr_runtime"

[Messages]
FinishedLabel=El OCR está instalado. Úsalo desde Prospecciones en SINCAL Suite. No se crearon accesos ni se modificaron tus proyectos.
