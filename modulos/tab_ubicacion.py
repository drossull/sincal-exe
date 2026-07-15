import os
import zipfile
import json
import math
import xml.etree.ElementTree as ET
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageDraw

RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL")


class TabUbicacion(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.estructuras_gps = {}
        self.datos_mapas = {}
        self.cargar_bd_mapas()
        self.setup_ui()

    def cargar_bd_mapas(self):
        """Lee el JSON de mapas pre-calibrados desde la carpeta 'mapas'"""
        ruta_json = os.path.join(
            RUTA_LOCAL_APP, "mapas", "mapas_calibrados.json")
        if os.path.exists(ruta_json):
            try:
                with open(ruta_json, 'r', encoding='utf-8') as f:
                    self.datos_mapas = json.load(f)
            except Exception as e:
                self.parent_app.log(
                    f"[X] Error leyendo mapas_calibrados.json: {e}")

    def setup_ui(self):
        fuente_subtitulo = ("Consolas", 18, "bold")
        fuente_normal = ("Consolas", 12)

        # --- 1. Panel Superior: Carga de Datos KMZ ---
        frame_top = ctk.CTkFrame(
            self, fg_color="#1E1E1E", border_width=1, border_color="#444444", corner_radius=0)
        frame_top.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frame_top, text="CROQUIS DE UBICACIÓN GEOGRÁFICA",
                     font=fuente_subtitulo, text_color="#FFBF00").pack(side="left", padx=15, pady=15)

        self.btn_cargar_kmz = ctk.CTkButton(frame_top, text="🌍 Cargar KMZ de Google Earth", font=fuente_normal,
                                            fg_color="#444444", hover_color="#555555", corner_radius=0, command=self.cargar_kmz)
        self.btn_cargar_kmz.pack(side="right", padx=15, pady=15)

        self.lbl_kmz_status = ctk.CTkLabel(
            frame_top, text="KMZ: No cargado", font=fuente_normal, text_color="#888888")
        self.lbl_kmz_status.pack(side="right", padx=(15, 0), pady=15)

        # --- 2. Panel Central: Selección Automatizada ---
        frame_main = ctk.CTkFrame(
            self, fg_color="#1E1E1E", border_width=1, border_color="#444444", corner_radius=0)
        frame_main.pack(fill="both", expand=True, padx=20, pady=5)

        # A. Selector de Estructura (KMZ)
        ctk.CTkLabel(frame_main, text="1. Seleccionar Enlace (desde KMZ):", font=fuente_normal,
                     text_color="#007FFF").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        self.combo_estructuras = ctk.CTkComboBox(frame_main, font=fuente_normal, width=400, values=[
                                                 "Cargue un archivo KMZ..."], state="disabled", command=self.actualizar_coordenadas_ui)
        self.combo_estructuras.grid(
            row=0, column=1, columnspan=3, sticky="w", padx=10, pady=(20, 10))

        ctk.CTkLabel(frame_main, text="Latitud GPS:", font=fuente_normal).grid(
            row=1, column=0, sticky="w", padx=20, pady=5)
        self.lbl_lat_val = ctk.CTkLabel(
            frame_main, text="---", font=fuente_normal, text_color="#CCCCCC")
        self.lbl_lat_val.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(frame_main, text="Longitud GPS:", font=fuente_normal).grid(
            row=1, column=2, sticky="w", padx=20, pady=5)
        self.lbl_lon_val = ctk.CTkLabel(
            frame_main, text="---", font=fuente_normal, text_color="#CCCCCC")
        self.lbl_lon_val.grid(row=1, column=3, sticky="w", padx=10, pady=5)

        # B. Selector de Mapa Calibrado (JSON)
        ctk.CTkLabel(frame_main, text="2. Seleccionar Mapa Base MOP:", font=fuente_normal,
                     text_color="#007FFF").grid(row=2, column=0, sticky="w", padx=20, pady=(25, 10))

        lista_mapas = list(self.datos_mapas.keys()) if self.datos_mapas else [
            "Falta sincronizar mapas_calibrados.json"]
        self.combo_mapas = ctk.CTkComboBox(
            frame_main, font=fuente_normal, width=400, values=lista_mapas)
        self.combo_mapas.grid(row=2, column=1, columnspan=3,
                              sticky="w", padx=10, pady=(25, 10))
        if not self.datos_mapas:
            self.combo_mapas.configure(state="disabled")

        # --- NUEVO: C. Controles de Micro-Ajuste Manual ---
        ctk.CTkLabel(frame_main, text="3. Micro-Ajuste en Píxeles (Opcional):", font=fuente_normal,
                     text_color="#007FFF").grid(row=3, column=0, sticky="w", padx=20, pady=(15, 5))

        frame_ajustes = ctk.CTkFrame(frame_main, fg_color="transparent")
        frame_ajustes.grid(row=4, column=0, columnspan=4,
                           sticky="w", padx=20, pady=(0, 20))

        # Ajuste X (Este / Oeste)
        ctk.CTkLabel(frame_ajustes, text="Este (+) / Oeste (-):",
                     font=fuente_normal).pack(side="left", padx=(0, 10))
        self.ent_ajuste_x = ctk.CTkEntry(
            frame_ajustes, font=fuente_normal, width=60, corner_radius=0)
        self.ent_ajuste_x.pack(side="left", padx=(0, 30))
        self.ent_ajuste_x.insert(0, "0")

        # Ajuste Y (Sur / Norte) -> Recordar que en imágenes +Y es hacia abajo (Sur)
        ctk.CTkLabel(frame_ajustes, text="Sur (+) / Norte (-):",
                     font=fuente_normal).pack(side="left", padx=(0, 10))
        self.ent_ajuste_y = ctk.CTkEntry(
            frame_ajustes, font=fuente_normal, width=60, corner_radius=0)
        self.ent_ajuste_y.pack(side="left", padx=(0, 20))
        self.ent_ajuste_y.insert(0, "0")

        # --- 3. Botón de Acción ---
        self.btn_generar_croquis = ctk.CTkButton(self, text="🗺️ GENERAR CROQUIS DE UBICACIÓN", font=fuente_subtitulo, fg_color="#007FFF",
                                                 hover_color="#0066CC", text_color="#FFFFFF", corner_radius=0, height=45, command=self.generar_croquis_png)
        self.btn_generar_croquis.pack(fill="x", padx=20, pady=(10, 20))

    def cargar_kmz(self):
        ruta_kmz = filedialog.askopenfilename(
            title="Seleccionar Archivo KMZ de Google Earth", filetypes=[("Google Earth KMZ", "*.kmz")])
        if not ruta_kmz:
            return

        try:
            with zipfile.ZipFile(ruta_kmz, 'r') as z:
                kml_filename = [f for f in z.namelist(
                ) if f.lower().endswith('.kml')][0]
                with z.open(kml_filename) as f:
                    kml_data = f.read()

            root = ET.fromstring(kml_data)
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]

            self.estructuras_gps.clear()
            for placemark in root.findall('.//Placemark'):
                name_elem = placemark.find('name')
                coord_elem = placemark.find('.//coordinates')
                if name_elem is not None and coord_elem is not None:
                    nombre = name_elem.text.strip()
                    coords_str = coord_elem.text.strip().split(',')
                    if len(coords_str) >= 2:
                        self.estructuras_gps[nombre] = (
                            float(coords_str[1]), float(coords_str[0]))

            if self.estructuras_gps:
                lista_nombres = sorted(list(self.estructuras_gps.keys()))
                self.combo_estructuras.configure(
                    values=lista_nombres, state="normal")
                self.combo_estructuras.set(lista_nombres[0])
                self.actualizar_coordenadas_ui(lista_nombres[0])

                self.lbl_kmz_status.configure(
                    text=f"KMZ: {os.path.basename(ruta_kmz)}", text_color="#007FFF")
            else:
                messagebox.showwarning(
                    "KMZ Vacío", "No se encontraron puntos en el KMZ.")
        except Exception as e:
            messagebox.showerror("Error KMZ", f"Fallo al procesar:\\n{e}")

    def actualizar_coordenadas_ui(self, nombre_seleccionado):
        if nombre_seleccionado in self.estructuras_gps:
            # 1. Actualiza los textos de la UI con las coordenadas exactas
            lat, lon = self.estructuras_gps[nombre_seleccionado]
            self.lbl_lat_val.configure(text=f"{lat:.6f}°")
            self.lbl_lon_val.configure(text=f"{lon:.6f}°")

            # 2. Resetea amablemente el menú para que elijas la región
            # (No fuerza ninguna opción matemática, tú decides)
            if self.datos_mapas:
                self.combo_mapas.set("Seleccione Mapa Base...")

    def generar_croquis_png(self):
        nombre_sel = self.combo_estructuras.get()
        mapa_sel = self.combo_mapas.get()

        if nombre_sel not in self.estructuras_gps:
            return messagebox.showerror("Error", "Seleccione un enlace válido.")
        if mapa_sel not in self.datos_mapas:
            return messagebox.showerror("Error", "Seleccione un mapa válido calibrado.")

        datos_calibracion = self.datos_mapas[mapa_sel]
        ruta_mapa_base = os.path.join(
            RUTA_LOCAL_APP, "mapas", datos_calibracion["archivo"])

        if not os.path.exists(ruta_mapa_base):
            return messagebox.showerror("Archivo Faltante", f"No se encontró la imagen base:\n{ruta_mapa_base}\nAsegúrate de sincronizar la aplicación.")

        # --- SELECCIÓN DE RUTA DE GUARDADO ---
        nombre_limpio = "".join(
            c for c in nombre_sel if c.isalnum() or c in (' ', '_', '-')).rstrip()
        nombre_sugerido = f"Ubicacion_{nombre_limpio}.png"

        ruta_salida = filedialog.asksaveasfilename(
            title="Guardar Croquis de Ubicación",
            initialfile=nombre_sugerido,
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")]
        )

        if not ruta_salida:
            return  # El usuario canceló el guardado

        try:
            # 1. Extracción de datos del JSON
            lat1_geo, lon1_geo = datos_calibracion["pt1_geo"]
            x1_px, y1_px = datos_calibracion["pt1_pixel"]
            lat2_geo, lon2_geo = datos_calibracion["pt2_geo"]
            x2_px, y2_px = datos_calibracion["pt2_pixel"]

            # 2. Capturar el Micro-Ajuste de la Interfaz GUI
            try:
                gui_ajuste_x = float(self.ent_ajuste_x.get())
                gui_ajuste_y = float(self.ent_ajuste_y.get())
            except ValueError:
                gui_ajuste_x = 0
                gui_ajuste_y = 0

            # 3. Sumar el ajuste del JSON + el ajuste manual de la interfaz
            ajuste_x = datos_calibracion.get("ajuste_x", 0) + gui_ajuste_x
            ajuste_y = datos_calibracion.get("ajuste_y", 0) + gui_ajuste_y

            lat_target, lon_target = self.estructuras_gps[nombre_sel]

            # 4. Motor de Interpolación Lineal + Ajuste Total
            escala_x = (x2_px - x1_px) / (lon2_geo - lon1_geo)
            x_final = x1_px + (lon_target - lon1_geo) * escala_x + ajuste_x

            escala_y = (y2_px - y1_px) / (lat2_geo - lat1_geo)
            y_final = y1_px + (lat_target - lat1_geo) * escala_y + ajuste_y

            # 5. Dibujo
            with Image.open(ruta_mapa_base) as img:
                img_rgba = img.convert("RGB")
                from PIL import ImageDraw  # Asegurarnos que está importado localmente si falla arriba
                draw = ImageDraw.Draw(img_rgba)

                r = 15
                bbox = [x_final - r, y_final - r, x_final + r, y_final + r]
                draw.ellipse(bbox, fill=(0, 0, 0), outline=(0, 0, 0), width=4)

                r_in = 4
                bbox_in = [x_final - r_in, y_final -
                           r_in, x_final + r_in, y_final + r_in]
                draw.ellipse(bbox_in, fill=(255, 0, 0))

                img_rgba.save(ruta_salida, "PNG")

            messagebox.showinfo(
                "Éxito", f"¡Croquis guardado correctamente en:\n{ruta_salida}")

            # NUEVO: Abrir la carpeta contenedora automáticamente
            import os
            os.startfile(os.path.dirname(ruta_salida))

        except Exception as e:
            messagebox.showerror(
                "Error", f"Fallo al generar el croquis:\n{str(e)}")
