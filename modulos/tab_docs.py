import os
import customtkinter as ctk

RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL")


class TabDocs(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.setup_ui()

    def setup_ui(self):
        fuente_subtitulo = ("Consolas", 18, "bold")
        fuente_normal = ("Consolas", 12)
        fuente_menu = ("Consolas", 13)
        color_texto = "#CCCCCC"
        color_titulo = "#FFBF00"

        m = ctk.CTkFrame(self, fg_color="transparent")
        m.pack(fill="both", expand=True, padx=10, pady=10)

        self.menu_container = ctk.CTkFrame(
            m, width=220, fg_color="transparent")
        self.menu_container.pack(side="left", fill="y")

        ctk.CTkFrame(m, width=1, fg_color="#555555").pack(
            side="left", fill="y", padx=15)

        c_cont = ctk.CTkFrame(m, fg_color="transparent")
        c_cont.pack(side="right", fill="both", expand=True)

        self.lbl_wiki_title = ctk.CTkLabel(
            c_cont, text="Seleccione un tema", font=fuente_subtitulo, text_color=color_titulo)
        self.lbl_wiki_title.pack(anchor="w", padx=20, pady=(10, 0))

        self.txt_wiki_content = ctk.CTkTextbox(
            c_cont, font=fuente_normal, fg_color="transparent", text_color=color_texto, wrap="word", border_width=0)
        self.txt_wiki_content.pack(fill="both", expand=True, padx=20, pady=10)

        opciones = [
            ("README", self.mostrar_readme),
            ("INICIO AUTOMÁTICO", self.mostrar_comandos_lisp),
            ("COMANDOS LISP", self.mostrar_comandos_lisp),
            ("PROCESAMIENTO MASIVO", self.mostrar_procesamiento_lote)
        ]

        for t, cmd in opciones:
            lbl = ctk.CTkLabel(self.menu_container, text=t,
                               font=fuente_menu, text_color=color_texto, cursor="hand2")
            lbl.pack(fill="x", pady=8, padx=10)
            lbl.bind("<Button-1>", lambda e, c=cmd: c())

    def mostrar_texto_wiki(self, t, c):
        self.lbl_wiki_title.configure(text=t.upper())
        self.txt_wiki_content.configure(state="normal")
        self.txt_wiki_content.delete("1.0", "end")
        self.txt_wiki_content.insert("0.0", c)
        self.txt_wiki_content.configure(state="disabled")

    def mostrar_readme(self):
        r = os.path.join(RUTA_LOCAL_APP, "README.md")
        self.mostrar_texto_wiki("README", open(r, 'r', encoding='utf-8').read()
                                if os.path.exists(r) else "No disponible. Actualiza la aplicación.")

    def mostrar_comandos_lisp(self):
        self.mostrar_texto_wiki("Comandos", "Diccionario de comandos LISP.")

    def mostrar_procesamiento_lote(self):
        self.mostrar_texto_wiki(
            "Lotes", "Scripts masivos por PowerShell corporativo.")
