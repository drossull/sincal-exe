@echo off
title Compilador SINCAL
echo ===================================================
echo     COMPILANDO SINCAL.EXE (PyInstaller)
echo ===================================================
echo.

rem 1. Limpiar basura de compilaciones anteriores
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "SINCAL.spec" del /q "SINCAL.spec"

echo Limpieza completada. Iniciando empaquetado...
echo.

rem 2. Compilar el ejecutable
rem --noconfirm: Sobrescribe sin preguntar
rem --onefile: Crea un solo archivo .exe
rem --windowed: Oculta la consola negra al abrir el programa
rem --icon: Asigna el icono al archivo de Windows
rem --add-data: Mete el icono dentro del .exe para la barra de titulo
rem --name: Nombre final del archivo

pyinstaller --noconfirm --onefile --windowed --icon "logo.ico" --name "SINCAL" --add-data "logo.ico;." main.py

echo.
echo ===================================================
echo   COMPILACION FINALIZADA
echo   Revisa la carpeta "dist", ahi estara tu SINCAL.exe
echo ===================================================
pause