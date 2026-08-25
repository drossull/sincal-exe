import importlib
import tkinter as tk
from tkinter import messagebox
from sincal.runtime import asegurar_directorios
from sincal.diagnostics import record_incident

# --- IMPORTACIONES FANTASMA PARA EL COMPILADOR (OBLIGATORIO) ---
import customtkinter
import win32com.client
import pythoncom
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
        from sincal import app
        importlib.reload(app)
        app.arrancar()
    except Exception as e:
        record_incident("inicio_aplicacion", "error", {"error": str(e)})
        mostrar_error_critico("SINCAL - Error de Núcleo",
                              f"El núcleo gráfico falló al iniciar. Revisa el detalle técnico y reinstala SINCAL si faltan recursos locales.\n\nDetalle técnico:\n{e}")


if __name__ == "__main__":
    iniciar()
