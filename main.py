import os
import sys
import ctypes
import requests
import importlib
import tkinter as tk
from tkinter import messagebox

# --- IMPORTACIONES FANTASMA PARA EL COMPILADOR (OBLIGATORIO) ---
import customtkinter
import win32com.client
import pythoncom
import pystray
from PIL import Image
# ----------------------------------------------------------------


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL")
os.makedirs(RUTA_LOCAL_APP, exist_ok=True)
sys.path.insert(0, RUTA_LOCAL_APP)


def mostrar_error_critico(titulo, mensaje):
    """Muestra un pop-up de error visual sin necesitar la consola negra"""
    root = tk.Tk()
    root.withdraw()  # Ocultamos la ventana base invisible
    messagebox.showerror(titulo, mensaje)
    root.destroy()


def iniciar():
    ruta_nucleo = os.path.join(RUTA_LOCAL_APP, "core_sincal.py")

    if not os.path.exists(ruta_nucleo):
        try:
            url_base = "https://raw.githubusercontent.com/drossull/sincal-exe/main/"
            r = requests.get(url_base + "version.json").json()
            archivos = r.get("archivos", []) + ["README.md", "TUTORIAL.md"]

            for a in archivos:
                r_save = os.path.normpath(os.path.join(RUTA_LOCAL_APP, a))
                os.makedirs(os.path.dirname(r_save), exist_ok=True)
                res = requests.get(url_base + a)
                if res.status_code == 200:
                    modo = 'w' if a.lower().endswith(
                        ('.lsp', '.py', '.md', '.json', '.bat', '.ps1')) else 'wb'
                    if modo == 'w':
                        with open(r_save, 'w', encoding='utf-8', errors='ignore') as f:
                            f.write(res.text)
                    else:
                        with open(r_save, 'wb') as f:
                            f.write(res.content)
        except Exception as e:
            mostrar_error_critico(
                "SINCAL - Error de Red", f"Fallo al descargar los archivos iniciales desde la nube.\n\nDetalle técnico: {e}")
            return

    try:
        import core_sincal
        importlib.reload(core_sincal)
        core_sincal.arrancar()
    except Exception as e:
        mostrar_error_critico("SINCAL - Error de Núcleo",
                              f"El núcleo gráfico falló al iniciar. Verifica que todos los módulos estén subidos a GitHub.\n\nDetalle técnico:\n{e}")


if __name__ == "__main__":
    iniciar()
