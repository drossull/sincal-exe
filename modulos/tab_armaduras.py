import customtkinter as ctk
from modulos.estructural.mod_estribos import ModEstribos
from modulos.estructural.mod_travesanos import ModTravesanos

class TabArmaduras(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.setup_ui()

    def setup_ui(self):
        fuente_normal = ("Consolas", 12)

        # TABVIEW MAESTRO
        self.tab_maestro = ctk.CTkTabview(self, width=800, height=520, fg_color="transparent", segmented_button_selected_color="#007FFF")
        self.tab_maestro.pack(padx=20, pady=5, fill="both", expand=True)
        self.tab_maestro._segmented_button.configure(font=fuente_normal)

        tab_estribos = self.tab_maestro.add("1. Estribos")
        tab_travesanos = self.tab_maestro.add("2. Travesaños")

        # INYECCIÓN DE SUB-MÓDULOS
        self.vista_estribos = ModEstribos(tab_estribos, parent_app=self.parent_app, fg_color="transparent")
        self.vista_estribos.pack(fill="both", expand=True)

        self.vista_travesanos = ModTravesanos(tab_travesanos, parent_app=self.parent_app, fg_color="transparent")
        self.vista_travesanos.pack(fill="both", expand=True)