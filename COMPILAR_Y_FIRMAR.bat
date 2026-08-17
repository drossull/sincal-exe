@echo off
title Compilador y Firmador Automatico SINCAL
cls
echo ========================================================
echo   COMPILANDO Y FIRMANDO SINCAL SUITE (Gonzalo Mardones V.)
echo   Wrapper legado: ejecutando tools\build_release.ps1
echo ========================================================
echo.
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_release.ps1"
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% neq 0 (
    echo.
    echo [X] build_release.ps1 fallo con codigo %EXITCODE%.
    pause
    exit /b %EXITCODE%
)
echo.
echo ========================================================
echo   PROCESO TERMINADO CON EXITO.
echo ========================================================
pause