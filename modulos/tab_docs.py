import json

import customtkinter as ctk

from sincal_runtime import ruta_recurso


class TabDocs(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.temas = []
        self.setup_ui()
        self.recargar_documentacion()

    def setup_ui(self):
        self.fuente_subtitulo = ("Consolas", 18, "bold")
        self.fuente_normal = ("Consolas", 12)
        self.fuente_menu = ("Consolas", 12)
        self.color_texto = "#CCCCCC"
        self.color_titulo = "#FFBF00"

        marco = ctk.CTkFrame(self, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=10, pady=10)

        lateral = ctk.CTkFrame(marco, width=280, fg_color="transparent")
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)

        ctk.CTkLabel(
            lateral, text="MANUAL SINCAL", font=self.fuente_subtitulo,
            text_color=self.color_titulo,
        ).pack(anchor="w", padx=8, pady=(5, 8))

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

        ctk.CTkFrame(marco, width=1, fg_color="#555555").pack(
            side="left", fill="y", padx=15
        )

        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.pack(side="right", fill="both", expand=True)

        self.lbl_wiki_title = ctk.CTkLabel(
            contenido, text="Documentación", font=self.fuente_subtitulo,
            text_color=self.color_titulo,
        )
        self.lbl_wiki_title.pack(anchor="w", padx=20, pady=(10, 0))

        self.lbl_categoria = ctk.CTkLabel(
            contenido, text="", font=("Consolas", 11), text_color="#007FFF"
        )
        self.lbl_categoria.pack(anchor="w", padx=20, pady=(2, 0))

        self.txt_wiki_content = ctk.CTkTextbox(
            contenido, font=self.fuente_normal, fg_color="transparent",
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
        if not temas:
            ctk.CTkLabel(
                self.menu_container, text="No se encontraron temas.",
                font=self.fuente_normal, text_color="#888888",
            ).pack(anchor="w", padx=8, pady=10)
            return

        categoria_actual = None
        for tema in temas:
            categoria = tema.get("categoria", "Otros")
            if categoria != categoria_actual:
                categoria_actual = categoria
                ctk.CTkLabel(
                    self.menu_container, text=categoria.upper(),
                    font=("Consolas", 11, "bold"), text_color="#007FFF",
                ).pack(anchor="w", padx=8, pady=(12, 3))
            ctk.CTkButton(
                self.menu_container, text=tema.get("titulo", "Tema"),
                font=self.fuente_menu, fg_color="transparent", hover_color="#3A3A3A",
                text_color=self.color_texto, anchor="w", corner_radius=0,
                command=lambda seleccionado=tema: self.mostrar_tema(seleccionado),
            ).pack(fill="x", padx=4, pady=1)

    def mostrar_tema(self, tema):
        self.lbl_wiki_title.configure(text=tema.get("titulo", "Documentación").upper())
        self.lbl_categoria.configure(text=tema.get("categoria", ""))
        self.txt_wiki_content.configure(state="normal")
        self.txt_wiki_content.delete("1.0", "end")
        self.txt_wiki_content.insert("1.0", tema.get("contenido", ""))
        self.txt_wiki_content.configure(state="disabled")
        self.txt_wiki_content.yview_moveto(0)
