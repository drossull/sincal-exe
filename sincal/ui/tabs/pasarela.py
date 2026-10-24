"""Puerta de entrada al módulo opcional; el editor se ejecuta por separado."""
from pathlib import Path
import threading
import webbrowser
from tkinter import TclError, filedialog, messagebox
from urllib.parse import urlsplit

import customtkinter as ctk

from sincal.ui.scroll import SafeScrollableFrame
from sincal.ui.widgets import ShadowButton
from sincal.ui.theme import (
    COLOR_ACENTO, COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_SUAVE,
    FUENTE_NORMAL, FUENTE_SUBTITULO, FUENTE_TITULO, RADIO_CONTROL, RADIO_PANEL,
)


class TabPasarela(ctk.CTkFrame):
    def __init__(self, master, parent_app, on_status=None, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.on_status = on_status or (lambda status: None)
        self._running = False
        self._status = None
        self._package = None
        self.container = SafeScrollableFrame(self, fg_color="transparent", corner_radius=RADIO_PANEL)
        self.container.pack(fill="both", expand=True, padx=20, pady=16)
        self._label(self.container, "PASARELA BIM", FUENTE_TITULO, COLOR_ACENTO)
        self._label(self.container, "Diseña el recorrido de una pasarela de hormigón, configura sus elementos y genera el modelo BIM y sus vistas con FreeCAD. El editor se abre en el navegador de este equipo.")
        self.state_label = self._label(self.container, "Comprobando disponibilidad…", FUENTE_SUBTITULO, COLOR_ACENTO)
        self.details = self._label(self.container, "", color=COLOR_TEXTO_SUAVE)
        self.install_info = self._label(self.container, "", color=COLOR_TEXTO_SUAVE)
        source_actions = ctk.CTkFrame(self.container, fg_color="transparent")
        source_actions.pack(fill="x", padx=12)
        self.source_button = self._button(source_actions, "Ver publicación de SINCAL", self.open_release)
        actions = ctk.CTkFrame(self.container, fg_color="transparent")
        actions.pack(fill="x", pady=12)
        self.online_button = self._button(actions, "Instalar Pasarela BIM", self.install_online)
        self.open_button = self._button(actions, "Abrir editor", self.open_editor)
        self.close_button = self._button(actions, "Cerrar módulo", self.close_editor)
        self.refresh_button = self._button(actions, "Actualizar estado", self.refresh)
        self.message = self._label(self.container, "", color=COLOR_TEXTO_SUAVE)
        self._label(self.container, "La instalación directa descarga el módulo compatible con tu versión de SINCAL y comprueba sus archivos. FreeCAD se instala por separado.", color=COLOR_TEXTO_SUAVE)
        self.manual_button = ShadowButton(
            self.container,
            text="▸ Instalar o actualizar desde un ZIP local",
            command=self.toggle_manual,
            font=FUENTE_NORMAL,
            corner_radius=RADIO_CONTROL,
            width=360,
        )
        self.manual_button.pack(anchor="w", padx=12, pady=12)

        self.install_panel = ctk.CTkFrame(self.container, fg_color=COLOR_PANEL, corner_radius=RADIO_PANEL)
        self.install_panel.pack(fill="x", pady=20)
        self._label(self.install_panel, "Instalación manual", FUENTE_SUBTITULO, COLOR_ACENTO)
        self._label(self.install_panel, "Si ya tienes el paquete del módulo, selecciónalo aquí para instalarlo sin descargarlo de nuevo.")
        self._label(self.install_panel, "Para actualizar un módulo abierto, guarda el JSON y usa «Cerrar módulo». Cerrar sólo la pestaña del navegador no detiene el módulo.", color=COLOR_TEXTO_SUAVE)
        self.package_label = self._label(self.install_panel, "Ningún paquete seleccionado.", color=COLOR_TEXTO_SUAVE)
        install_actions = ctk.CTkFrame(self.install_panel, fg_color="transparent")
        install_actions.pack(fill="x", padx=12, pady=12)
        self.choose_button = self._button(install_actions, "Elegir paquete ZIP", self.choose_package)
        self.install_button = self._button(install_actions, "Instalar paquete", self.install_package)
        self._label(self.install_panel, "Máximo 150 MiB. SINCAL comprueba el manifiesto y los archivos del paquete antes de instalarlo.", color=COLOR_TEXTO_SUAVE)
        self.install_panel.pack_forget()
        self._controls()

    @staticmethod
    def _label(parent, text, font=FUENTE_NORMAL, color=COLOR_TEXTO):
        label = ctk.CTkLabel(parent, text=text, font=font, text_color=color, wraplength=760, justify="left", anchor="w")
        label.pack(fill="x", padx=12, pady=7)
        return label

    @staticmethod
    def _button(parent, text, command):
        button = ShadowButton(parent, text=text, command=command, font=FUENTE_NORMAL, corner_radius=RADIO_CONTROL)
        button.pack(side="left", padx=(0, 12), pady=4)
        return button

    @staticmethod
    def _backend(name, *args):
        # Keep the optional editor and its dependencies out of SINCAL startup.
        from sincal import optional_modules
        return getattr(optional_modules, name)(*args)

    def _controls(self):
        status = self._status or {}
        self.online_button.configure(state="normal" if not self._running and status.get("online_install_available") and not status.get("running") else "disabled")
        visible, hidden = (self.open_button, self.online_button) if status.get("installed") else (self.online_button, self.open_button)
        hidden.pack_forget()
        if not visible.winfo_manager():
            visible.pack(side="left", padx=(0, 12), pady=4, before=self.close_button)
        self.source_button.configure(state="normal" if self._release_url() else "disabled")
        self.open_button.configure(state="normal" if not self._running and (self._status or {}).get("installed") else "disabled")
        self.close_button.configure(state="normal" if not self._running and (self._status or {}).get("running") else "disabled")
        self.refresh_button.configure(state="disabled" if self._running else "normal")
        self.choose_button.configure(state="disabled" if self._running else "normal")
        self.install_button.configure(state="normal" if not self._running and self._package and not (self._status or {}).get("running") else "disabled")

    def _run(self, message, action, on_success):
        if self._running:
            return
        self._running = True
        self.message.configure(text=message)
        self._controls()

        def work():
            try:
                value = action()
            except Exception as error:
                self.parent_app._ui(self._finish, None, str(error), on_success)
            else:
                self.parent_app._ui(self._finish, value, None, on_success)

        threading.Thread(target=work, daemon=True).start()

    def _finish(self, value, error, on_success):
        if not self.winfo_exists():
            return
        self._running = False
        if error:
            if self._status is None:
                self.state_label.configure(text="No se pudo comprobar el módulo.")
            self.message.configure(text=error)
        else:
            on_success(value)
        self._controls()

    def refresh(self):
        self._run("Comprobando disponibilidad…", lambda: self._backend("pasarela_status"), self._show_status)

    def _show_status(self, status):
        self._status = status
        self.on_status(status)
        installed = status.get("installed", False)
        development = status.get("source") == "development"
        self.state_label.configure(text=("Disponible en desarrollo" if development else "Módulo instalado") if installed else "Módulo no instalado")
        source = {"development": "Carpeta de desarrollo", "user": "Instalado para este usuario", "application": "Incluido con esta instalación"}.get(status.get("source"), "Sin instalar")
        freecad = "Disponible" if status.get("freecad_available") else "No detectado: necesario para generar el modelo BIM"
        self.details.configure(text=f"Versión: {status.get('version') or 'No disponible'}\nOrigen: {source}\nFreeCAD: {freecad}")
        self.message.configure(text=status.get("message") or "")
        self.install_info.configure(text=status.get("install_message") or "Puedes instalar el módulo desde un paquete ZIP local.")
        self.install_button.configure(text="Actualizar desde paquete" if installed else "Instalar paquete")

    def _release_url(self):
        value = str((self._status or {}).get("release_url") or "")
        parsed = urlsplit(value)
        return value if parsed.scheme == "https" and parsed.netloc == "github.com" and (parsed.path == "/drossull/sincal-updates/releases" or parsed.path.startswith("/drossull/sincal-updates/releases/")) else None

    def open_release(self):
        url = self._release_url()
        if url:
            webbrowser.open(url)

    def install_online(self):
        self._run("Descargando, comprobando e instalando Pasarela BIM…", lambda: self._backend("install_pasarela_online"), self._show_status)

    def toggle_manual(self):
        if self.install_panel.winfo_manager():
            self.install_panel.pack_forget()
            self.manual_button.configure(text="▸ Instalar o actualizar desde un ZIP local")
        else:
            self.install_panel.pack(fill="x", pady=20)
            self.manual_button.configure(text="▾ Instalar o actualizar desde un ZIP local")

    def open_editor(self):
        def launch():
            result = self._backend("launch_pasarela")
            return self._backend("pasarela_status"), result.get("message") or "Se ha solicitado abrir el editor en el navegador."

        self._run("Abriendo Pasarela BIM…", launch, self._after_command)

    def close_editor(self):
        if not messagebox.askokcancel("Cerrar Pasarela BIM", "Guarda el JSON de tu pasarela antes de cerrar. El editor dejará de estar disponible hasta que vuelvas a abrirlo. ¿Cerrar el módulo?", parent=self):
            return

        def close():
            self._backend("close_pasarela")
            return self._backend("pasarela_status"), "Módulo cerrado. Puedes instalar una actualización o volver a abrirlo."

        self._run("Cerrando Pasarela BIM…", close, self._after_command)

    def _after_command(self, value):
        status, message = value
        self._show_status(status)
        self.message.configure(text=message)

    def choose_package(self):
        path = filedialog.askopenfilename(parent=self, title="Paquete de Pasarela BIM", filetypes=[("Paquete ZIP", "*.zip")])
        if not path:
            return
        try:
            package = Path(path)
            if package.suffix.lower() != ".zip" or not 0 < package.stat().st_size <= 150 * 1024 * 1024:
                raise ValueError("Selecciona un ZIP no vacío de hasta 150 MiB.")
            self._package = package
            self.package_label.configure(text=f"{package.name} · {package.stat().st_size / 1024 / 1024:.1f} MiB")
        except (OSError, ValueError) as error:
            self._package = None
            self.package_label.configure(text="Ningún paquete seleccionado.")
            self.message.configure(text=str(error))
        self._controls()

    def install_package(self):
        if not self._package:
            return
        package = self._package

        def installed(status):
            self._package = None
            self.package_label.configure(text="Ningún paquete seleccionado.")
            self._show_status(status)

        self._run("Instalando el paquete…", lambda: self._backend("install_pasarela_package", package), installed)

    def ir_a_seccion(self, anchor):
        try:
            if anchor == "instalar" and not self.install_panel.winfo_manager():
                self.toggle_manual()
            self.update_idletasks()
            offset = self.install_panel.winfo_y() if anchor == "instalar" else 0
            total = max(1, self.container._parent_frame.winfo_reqheight())
            self.container._parent_canvas.yview_moveto(max(0, min(1, offset / total)))
        except (AttributeError, TclError):
            return
