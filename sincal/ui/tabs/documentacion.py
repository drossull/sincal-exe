import json
import re

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
    FUENTE_SUBTITULO_PEQUENO,
    FUENTE_TITULO_PEQUENO,
    RADIO_CONTROL,
    RADIO_PANEL,
)


class TabDocs(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.temas = []
        self._categoria_actual = None
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
            text_color=self.color_titulo, anchor="w", justify="left", wraplength=760,
        )
        self.lbl_wiki_title.pack(anchor="w", padx=20, pady=(10, 0))

        self.lbl_categoria = ctk.CTkLabel(
            contenido, text="", font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_ACENTO
        )
        self.lbl_categoria.pack(anchor="w", padx=20, pady=(2, 0))

        self.txt_wiki_content = ctk.CTkTextbox(
            contenido, font=self.fuente_normal, fg_color=COLOR_PANEL,
            text_color=self.color_texto, wrap="word", border_width=0,
            corner_radius=0,
        )
        self.txt_wiki_content.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_wiki_content._textbox.configure(
            padx=22, pady=18, spacing1=2, spacing3=7,
        )

    def recargar_documentacion(self):
        self.temas = self._cargar_temas()
        if self.temas:
            self.mostrar_tema(self.temas[0])

    @staticmethod
    def _titulo_menu(titulo):
        """Acorta títulos sin perder el concepto que identifica cada tema."""
        replacements = {
            "README — Visión general": "Visión general",
            "Primer inicio y preparación": "Primer inicio",
            "Actualizaciones del programa y recursos": "Actualizaciones",
            "Temas y accesibilidad visual": "Temas y accesibilidad",
            "Integración con AutoCAD y ZWCAD": "AutoCAD y ZWCAD",
            "Inicio automático SINCAL_STARTUP": "Inicio automático",
            "Master DWG y estándares anotativos": "Master DWG",
            "Qué contiene cada carpeta": "Carpetas y recursos",
            "Flujo de renombrado y precauciones": "Renombrado",
            "Buscar, reemplazar y convertir DXF": "Buscar y reemplazar",
            "Comandos en planos abiertos": "Comandos en vivo",
            "Armaduras de estribos y travesaños": "Generador de armadura",
            "Estribos: anotaciones y despiece de zapata": "Anotaciones y despiece",
            "Estribos: flujo controlado de generación": "Generación de estribos",
            "Estribos: vistas, capas y lectura de fierros": "Vistas y capas",
            "Glosario de estribos y armaduras": "Glosario estructural",
            "Croquis desde Google Earth KMZ": "Croquis desde KMZ",
            "Diagnóstico e informe de soporte": "Diagnóstico y soporte",
            "Solución de problemas frecuentes": "Solución de problemas",
        }
        result = replacements.get(titulo, titulo)
        return result if len(result) <= 34 else result[:33].rstrip() + "…"

    def obtener_navegacion(self, categoria=None, grupo=None):
        """Crea un índice jerárquico que nunca necesita scrollbar."""
        if categoria is None:
            categorias = []
            for tema in self.temas:
                name = tema.get("categoria") or "General"
                if name not in categorias:
                    categorias.append(name)
            return tuple((name, f"categoria::{name}") for name in categorias)

        topics = [tema for tema in self.temas if (tema.get("categoria") or "General") == categoria]
        if grupo is None and len(topics) > 14:
            entries = [("← Secciones", "categorias")]
            for start in range(0, len(topics), 12):
                chunk = topics[start:start + 12]
                first = self._titulo_menu(chunk[0].get("titulo", "Tema"))
                last = self._titulo_menu(chunk[-1].get("titulo", "Tema"))
                entries.append((f"{first} – {last}", f"grupo::{categoria}::{start}"))
            return tuple(entries)

        if grupo is not None:
            topics = topics[grupo:grupo + 12]
            back = (f"← {categoria}", f"volver-cat::{categoria}")
        else:
            back = ("← Secciones", "categorias")
        return (back,) + tuple(
            (self._titulo_menu(tema.get("titulo", "Tema")), tema.get("id", ""))
            for tema in topics if tema.get("id"))

    def mostrar_tema_por_id(self, topic_id):
        if topic_id == "categorias":
            self._categoria_actual = None
            self.parent_app.configurar_navegacion_pagina(
                "documentacion", entries=self.obtener_navegacion())
            return
        if topic_id.startswith("categoria::"):
            categoria = topic_id.split("::", 1)[1]
            self._categoria_actual = categoria
            topics = [tema for tema in self.temas if (tema.get("categoria") or "General") == categoria]
            if topics:
                self.mostrar_tema(topics[0])
            self.parent_app.configurar_navegacion_pagina(
                "documentacion", entries=self.obtener_navegacion(categoria))
            return
        if topic_id.startswith("grupo::"):
            _prefix, categoria, start = topic_id.split("::", 2)
            start = int(start)
            topics = [tema for tema in self.temas if (tema.get("categoria") or "General") == categoria]
            if start < len(topics):
                self.mostrar_tema(topics[start])
            self.parent_app.configurar_navegacion_pagina(
                "documentacion", entries=self.obtener_navegacion(categoria, start))
            return
        if topic_id.startswith("volver-cat::"):
            categoria = topic_id.split("::", 1)[1]
            self.parent_app.configurar_navegacion_pagina(
                "documentacion", entries=self.obtener_navegacion(categoria))
            return
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
        text_widget = self.txt_wiki_content._textbox
        tk_font = lambda font: (font[0], -abs(font[1]), *font[2:])
        text_widget.tag_configure(
            "doc_h1", font=tk_font(FUENTE_TITULO_PEQUENO), spacing1=12, spacing3=8)
        text_widget.tag_configure(
            "doc_h2", font=tk_font(FUENTE_SUBTITULO), spacing1=10, spacing3=6)
        text_widget.tag_configure(
            "doc_h3", font=tk_font(FUENTE_SUBTITULO_PEQUENO), spacing1=8, spacing3=4)
        text_widget.tag_configure(
            "doc_list", lmargin1=18, lmargin2=38, spacing1=2, spacing3=3)
        text_widget.tag_configure("doc_body", spacing3=5)
        for raw_line in tema.get("contenido", "").splitlines():
            stripped = raw_line.strip()
            clean = stripped.replace("**", "")
            if stripped.startswith("### "):
                text_widget.insert("end", clean[4:] + "\n", "doc_h3")
            elif stripped.startswith("## "):
                text_widget.insert("end", clean[3:] + "\n", "doc_h2")
            elif stripped.startswith("# "):
                text_widget.insert("end", clean[2:] + "\n", "doc_h1")
            elif stripped.startswith(("- ", "• ")):
                text_widget.insert("end", "• " + clean[2:] + "\n", "doc_list")
            elif re.match(r"^\d+[.)]\s+", stripped):
                text_widget.insert("end", clean + "\n", "doc_list")
            elif clean and clean == clean.upper() and len(clean) <= 72:
                text_widget.insert("end", clean + "\n", "doc_h3")
            else:
                text_widget.insert("end", clean + "\n", "doc_body")
        self.txt_wiki_content.configure(state="disabled")
        self.txt_wiki_content.yview_moveto(0)
        if hasattr(self.parent_app, "marcar_navegacion_pagina"):
            self.parent_app.marcar_navegacion_pagina(tema.get("id", ""))
