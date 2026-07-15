import os
import sys
import ctypes
import requests
import importlib

# --- IMPORTACIONES FANTASMA PARA EL COMPILADOR (OBLIGATORIO) ---
# Le decimos a PyInstaller que empaquete estas librerías pesadas en el .exe
import customtkinter
import win32com.client
import pythoncom
import pystray
from PIL import Image
# ----------------------------------------------------------------

# 1. FORZAR MODO ADMINISTRADOR
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# 2. DEFINIR LA BÓVEDA APPDATA
RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL")
os.makedirs(RUTA_LOCAL_APP, exist_ok=True)

# Obligamos a Python a leer los archivos de APPDATA con prioridad
sys.path.insert(0, RUTA_LOCAL_APP)

def iniciar():
    ruta_nucleo = os.path.join(RUTA_LOCAL_APP, "core_sincal.py")
    
    # 3. PRIMERA INSTALACIÓN: Si no existe el núcleo, descarga todo el programa base
    if not os.path.exists(ruta_nucleo):
        print("[SINCAL] Primera instalación detectada. Descargando entorno desde la nube...")
        try:
            url_base = "https://raw.githubusercontent.com/drossull/sincal-exe/main/"
            r = requests.get(url_base + "version.json").json()
            archivos = r.get("archivos", []) + ["README.md", "TUTORIAL.md"]
            
            for a in archivos:
                r_save = os.path.normpath(os.path.join(RUTA_LOCAL_APP, a))
                os.makedirs(os.path.dirname(r_save), exist_ok=True)
                res = requests.get(url_base + a)
                if res.status_code == 200:
                    modo = 'w' if a.lower().endswith(('.lsp', '.py', '.md', '.json', '.bat')) else 'wb'
                    if modo == 'w':
                        with open(r_save, 'w', encoding='utf-8', errors='ignore') as f:
                            f.write(res.text)
                    else:
                        with open(r_save, 'wb') as f:
                            f.write(res.content)
            print("[OK] Entorno descargado.")
        except Exception as e:
            print(f"[X] Error de red al intentar descargar el entorno: {e}")
            input("Presione Enter para salir...")
            return
            
    # 4. Importar y arrancar el código dinámicamente
    try:
        import core_sincal
        importlib.reload(core_sincal) # Forzar recarga en memoria
        core_sincal.arrancar()
    except Exception as e:
        print(f"[X] Error iniciando núcleo gráfico: {e}")
        input("Presione Enter para salir...")

if __name__ == "__main__":
    iniciar()