import json

import customtkinter as ctk

from sincal_runtime import ruta_recurso
from sincal_ui import (
    COLOR_ACENTO,
    COLOR_MOSTAZA,
    COLOR_PANEL,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    FUENTE_MENU,
    FUENTE_NORMAL,
    FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO,
)


class TabDocs(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.temas = []
        self._menu_buttons = []
        self._panel_width = 300
        self.setup_ui()
        self.recargar_documentacion()

    def setup_ui(self):
        self.fuente_subtitulo = FUENTE_SUBTITULO
        self.fuente_normal = FUENTE_NORMAL
        self.fuente_menu = FUENTE_MENU
        self.color_texto = COLOR_TEXTO
        self.color_titulo = COLOR_MOSTAZA

        marco = ctk.CTkFrame(self, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=10, pady=10)
        self.marco = marco
        marco.grid_rowconfigure(0, weight=1)
        marco.grid_columnconfigure(0, minsize=self._panel_width)
        marco.grid_columnconfigure(2, weight=1)

        self.lateral = ctk.CTkFrame(marco, width=self._panel_width, fg_color="transparent")
        self.lateral.grid(row=0, column=0, sticky="nsew")
        self.lateral.grid_propagate(False)
        lateral = self.lateral

        ctk.CTkLabel(
            lateral, text="MANUAL SINCAL", font=self.fuente_subtitulo,
            text_color=self.color_titulo,
        ).pack(anchor="w", padx=8, pady=(5, 8))
        ctk.CTkLabel(
            lateral, text="Guías, recursos, módulos y comandos CAD.", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, wraplength=245, justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 12))

        self.busqueda = ctk.CTkEntry(
            lateral, placeholder_text="Buscar comando o herramienta...",
            font=self.fuente_normal, corner_radius=0,
        )
        self.busqueda.pack(fill="x", padx=8, pady=(0, 8))
        self.busqueda.bind("<KeyRelease>", self._filtrar_menu)

        self.menu_container = ctk.CTkScrollableFrame(
            lateral, fg_color="transparent", corner_radius=0
        )
        self.menu_container.pack(fill="both", expand=True)

        self.panel_grip = ctk.CTkFrame(
            marco, width=7, fg_color=COLOR_PANEL, corner_radius=0,
            cursor="sb_h_double_arrow",
        )
        self.panel_grip.grid(row=0, column=1, sticky="ns", padx=8)
        self.panel_grip.bind("<ButtonPress-1>", self._iniciar_redimension_panel)
        self.panel_grip.bind("<B1-Motion>", self._redimensionar_panel)

        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.grid(row=0, column=2, sticky="nsew")

        self.lbl_wiki_title = ctk.CTkLabel(
            contenido, text="Documentación", font=self.fuente_subtitulo,
            text_color=self.color_titulo,
        )
        self.lbl_wiki_title.pack(anchor="w", padx=20, pady=(10, 0))

        self.lbl_categoria = ctk.CTkLabel(
            contenido, text="", font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_ACENTO
        )
        self.lbl_categoria.pack(anchor="w", padx=20, pady=(2, 0))

        self.txt_wiki_content = ctk.CTkTextbox(
            contenido, font=self.fuente_normal, fg_color=COLOR_PANEL,
            text_color=self.color_texto, wrap="word", border_width=0,
        )
        self.txt_wiki_content.pack(fill="both", expand=True, padx=20, pady=10)

    def recargar_documentacion(self):
        self.temas = self._cargar_temas()
        self._render_menu(self.temas)
        if self.temas:
            self.mostrar_tema(self.temas[0])

    def _leer_texto(self, *partes):
        ruta = ruta_recurso(*partes)
        try:
            with open(ruta, "r", encoding="utf-8") as archivo:
                return archivo.read()
        except OSError:
            return "No disponible. Comprueba las actualizaciones de recursos CAD."

    def _cargar_temas(self):
        temas = [{
            "id": "readme", "categoria": "Inicio",
            "titulo": "README — Visión general",
            "contenido": self._leer_texto("README.md"),
            "tags": "inicio instalación actualización",
        }]
        ruta_tutoriales = ruta_recurso("tutoriales.json")
        try:
            with open(ruta_tutoriales, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except (OSError, ValueError, TypeError) as error:
            self.parent_app.log(f"[!] No se pudo cargar tutoriales.json: {error}")
            return temas

        if not isinstance(datos, dict):
            self.parent_app.log("[!] tutoriales.json no tiene una estructura válida.")
            return temas

        if datos.get("schema") != 2:
            for comando, detalle in datos.items():
                if isinstance(detalle, dict):
                    temas.append({
                        "id": comando, "categoria": "Comandos LISP",
                        "titulo": detalle.get("titulo", comando),
                        "contenido": detalle.get("descripcion", ""), "tags": comando,
                    })
            return temas

        temas.extend(datos.get("temas") or [])
        for comando, detalle in (datos.get("comandos_lisp") or {}).items():
            temas.append({
                "id": f"lisp-{comando}", "categoria": "Comandos LISP",
                "titulo": f"{comando} — {detalle.get('titulo', '')}".strip(" —"),
                "contenido": self._formatear_comando(comando, detalle),
                "tags": " ".join([comando] + list(detalle.get("tags") or [])),
            })
        return temas

    @staticmethod
    def _formatear_comando(comando, detalle):
        bloques = [f"COMANDO: {comando}\n\n{detalle.get('descripcion', '')}".strip()]
        pasos = detalle.get("pasos") or []
        if pasos:
            bloques.append("CÓMO SE USA\n\n" + "\n".join(
                f"{indice}. {paso}" for indice, paso in enumerate(pasos, 1)
            ))
        notas = detalle.get("notas") or []
        if notas:
            bloques.append("NOTAS Y PRECAUCIONES\n\n" + "\n".join(
                f"• {nota}" for nota in notas
            ))
        return "\n\n".join(bloques)

    def _filtrar_menu(self, _evento=None):
        consulta = self.busqueda.get().strip().lower()
        filtrados = self.temas if not consulta else [
            tema for tema in self.temas
            if consulta in " ".join([
                str(tema.get("titulo", "")), str(tema.get("categoria", "")),
                str(tema.get("tags", "")), str(tema.get("contenido", "")),
            ]).lower()
        ]
        self._render_menu(filtrados)

    def _render_menu(self, temas):
        for widget in self.menu_container.winfo_children():
            widget.destroy()
        self._menu_buttons = []
        if not temas:
            ctk.CTkLabel(
                self.menu_container, text="No se encontraron temas.",
                font=self.fuente_normal, text_color=COLOR_TEXTO_SUAVE,
            ).pack(anchor="w", padx=8, pady=10)
            return

        categoria_actual = None
        for tema in temas:
            categoria = tema.get("categoria", "Otros")
            if categoria != categoria_actual:
                categoria_actual = categoria
                ctk.CTkLabel(
                    self.menu_container, text=categoria.upper(),
                    font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_ACENTO,
                ).pack(anchor="w", padx=8, pady=(12, 3))
            button = ctk.CTkButton(
                self.menu_container, text=tema.get("titulo", "Tema"),
                font=self.fuente_menu, fg_color="transparent", hover_color=COLOR_PANEL,
                text_color=self.color_texto, anchor="w", corner_radius=0, height=44,
                command=lambda seleccionado=tema: self.mostrar_tema(seleccionado),
            )
            button.pack(fill="x", padx=4, pady=1)
            self._menu_buttons.append(button)
        self.after_idle(self._actualizar_wrap_menu)

    def _iniciar_redimension_panel(self, event):
        self._drag_origin = event.x_root
        self._drag_width = self._panel_width

    def _redimensionar_panel(self, event):
        delta = event.x_root - getattr(self, "_drag_origin", event.x_root)
        self._panel_width = max(230, min(520, getattr(self, "_drag_width", 300) + delta))
        self.lateral.configure(width=self._panel_width)
        self.marco.grid_columnconfigure(0, minsize=self._panel_width)
        self._actualizar_wrap_menu()

    def _actualizar_wrap_menu(self):
        wrap = max(170, self._panel_width - 54)
        for button in self._menu_buttons:
            label = getattr(button, "_text_label", None)
            if label is not None:
                label.configure(wraplength=wrap, justify="left")

    def mostrar_tema(self, tema):
        self.lbl_wiki_title.configure(text=tema.get("titulo", "Documentación").upper())
        self.lbl_categoria.configure(text=tema.get("categoria", ""))
        self.txt_wiki_content.configure(state="normal")
        self.txt_wiki_content.delete("1.0", "end")
        self.txt_wiki_content.insert("1.0", tema.get("contenido", ""))
        self.txt_wiki_content.configure(state="disabled")
        self.txt_wiki_content.yview_moveto(0)
