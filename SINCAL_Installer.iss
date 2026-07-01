[Setup]
AppName=SINCAL Suite
AppVersion=26.1.4
AppPublisher=Gonzalo Mardones V.
DefaultDirName={userappdata}\Estandar SINCAL
DefaultGroupName=SINCAL Suite
OutputDir=.\installer_output
OutputBaseFilename=Setup_SINCAL_v26
SetupIconFile=logo.ico
Compression=lzma
SolidCompression=yes
; Privilegios administrativos requeridos para instalar el certificado de seguridad
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 1. Archivos principales del programa (Cambia las rutas por tus rutas reales)
Source: "C:\Users\Usuario\Documents\GitHub\sincal-exe\dist\SINCAL.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\Usuario\Documents\GitHub\sincal-exe\SINCAL_Certificado.cer"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SINCAL Suite"; Filename: "{app}\SINCAL.exe"
Name: "{userdesktop}\SINCAL Suite"; Filename: "{app}\SINCAL.exe"; Tasks: desktopicon

[Run]
; --- EL TRUCO DE MAGIA ---
; Este comando instala el certificado de Gonzalo en la raíz de confianza de Windows en pleno proceso de instalación
Filename: "certutil.exe"; Parameters: "-addstore -f ""Root"" ""{app}\SINCAL_Certificado.cer"""; Flags: runhidden

; Iniciar el programa automáticamente al terminar
Filename: "{app}\SINCAL.exe"; Description: "{cm:LaunchProgram,SINCAL Suite}"; Flags: nowait postinstall skipifsilent