import importlib
import tkinter as tk
from tkinter import messagebox
from sincal_runtime import asegurar_directorios

# --- IMPORTACIONES FANTASMA PARA EL COMPILADOR (OBLIGATORIO) ---
import customtkinter
import win32com.client
import pythoncom
import pystray
from PIL import Image
# ----------------------------------------------------------------


def mostrar_error_critico(titulo, mensaje):
    """Muestra un pop-up de error visual sin necesitar la consola negra"""
    root = tk.Tk()
    root.withdraw()  # Ocultamos la ventana base invisible
    messagebox.showerror(titulo, mensaje)
    root.destroy()


def iniciar():
    asegurar_directorios()
    try:
        import core_sincal
        importlib.reload(core_sincal)
        core_sincal.arrancar()
    except Exception as e:
        mostrar_error_critico("SINCAL - Error de Núcleo",
                              f"El núcleo gráfico falló al iniciar. Revisa el detalle técnico y reinstala SINCAL si faltan recursos locales.\n\nDetalle técnico:\n{e}")


if __name__ == "__main__":
    iniciar()
