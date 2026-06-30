import os

print("[*] Iniciando compilación de SINCAL.exe...")

# Ejecutamos el comando exacto de PyInstaller
os.system("pyinstaller --name SINCAL --noconsole --onefile --icon=logo.ico --hidden-import pystray --hidden-import PIL main.py")

print("\n[OK] Proceso terminado. Revisa la carpeta 'dist'.")
input("Presiona Enter para salir...")