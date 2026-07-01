@echo off
title Compilador y Firmador Automatico SINCAL
cls
echo ========================================================
echo   COMPILANDO Y FIRMANDO SINCAL SUITE (Gonzalo Mardones V.)
echo ========================================================
echo.

echo [1/4] Ejecutando PyInstaller...
pyinstaller --noconfirm --onefile --windowed --icon="logo.ico" --name="SINCAL" "main.py"
if %errorlevel% neq 0 (
    echo [X] Error en PyInstaller. Proceso abortado.
    pause
    exit /b
)

echo.
echo [2/4] Firmando SINCAL.exe...
powershell -Command "$cert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object Subject -match 'Gonzalo Mardones'; Set-AuthenticodeSignature -FilePath 'dist\SINCAL.exe' -Certificate $cert -TimestampServer 'http://timestamp.digicert.com'"

echo.
echo [3/4] Compilando Instalador con Inno Setup (ISCC)...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" SINCAL_Installer.iss
if %errorlevel% neq 0 (
    echo [X] Error en Inno Setup. Proceso abortado.
    pause
    exit /b
)

echo.
echo [4/4] Firmando el Instalador Final (Setup)...
:: Agregamos un retraso de 2 segundos para asegurar que Inno Setup libere por completo el archivo del disco
timeout /t 2 /nobreak >nul
powershell -Command "$cert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object Subject -match 'Gonzalo Mardones'; Set-AuthenticodeSignature -FilePath 'installer_output\Setup_SINCAL_v26.exe' -Certificate $cert -TimestampServer 'http://timestamp.digicert.com'"

echo.
echo ========================================================
echo   PROCESO TERMINADO CON EXITO. TU INSTALADOR ESTA LISTO.
echo ========================================================
echo El archivo firmado se encuentra en: installer_output\Setup_SINCAL_v26.exe
echo.
pause