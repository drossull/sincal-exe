import json

import customtkinter as ctk

from sincal.runtime import ruta_recurso
from sincal.ui.theme import (
    COLOR_ACENTO,
    COLOR_BORDE,
    COLOR_MOSTAZA,
    COLOR_PANEL,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    FUENTE_MENU,
    FUENTE_NORMAL,
    FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO,
    RADIO_CONTROL,
    RADIO_PANEL,
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

        contenido = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0)
        contenido.pack(fill="both", expand=True, padx=20, pady=14)

        self.lbl_wiki_title = ctk.CTkLabel(
            contenido, text="DOCUMENTACIÓN", font=self.fuente_subtitulo,
            text_color=self.color_titulo,
        )
        self.lbl_wiki_title.pack(anchor="w", padx=20, pady=(10, 0))

        self.lbl_categoria = ctk.CTkLabel(
            contenido, text="", font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_ACENTO
        )
        self.lbl_categoria.pack(anchor="w", padx=20, pady=(2, 0))

        self.txt_wiki_content = ctk.CTkTextbox(
            contenido, font=self.fuente_normal, fg_color=COLOR_PANEL,
            text_color=self.color_texto, wrap="word", border_width=1,
            border_color=COLOR_BORDE, corner_radius=0,
        )
        self.txt_wiki_content.pack(fill="both", expand=True, padx=20, pady=10)

    def recargar_documentacion(self):
        self.temas = self._cargar_temas()
        if self.temas:
            self.mostrar_tema(self.temas[0])

    def obtener_navegacion(self):
        return tuple(
            (tema.get("titulo", "Tema"), tema.get("id", ""))
            for tema in self.temas if tema.get("id"))

    def mostrar_tema_por_id(self, topic_id):
        for tema in self.temas:
            if tema.get("id") == topic_id:
                self.mostrar_tema(tema)
                return

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

    def mostrar_tema(self, tema):
        self.lbl_wiki_title.configure(text=tema.get("titulo", "Documentación").upper())
        self.lbl_categoria.configure(text=tema.get("categoria", ""))
        self.txt_wiki_content.configure(state="normal")
        self.txt_wiki_content.delete("1.0", "end")
        self.txt_wiki_content.insert("1.0", tema.get("contenido", ""))
        self.txt_wiki_content.configure(state="disabled")
        self.txt_wiki_content.yview_moveto(0)
        if hasattr(self.parent_app, "marcar_navegacion_pagina"):
            self.parent_app.marcar_navegacion_pagina(tema.get("id", ""))
