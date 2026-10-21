@echo off
cd /d "%~dp0"
python -m pasarela_bim
if errorlevel 1 pause
