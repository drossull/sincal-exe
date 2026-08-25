import json
import math
import os
import threading
import xml.etree.ElementTree as ET
import zipfile
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from sincal.ui.icons import obtener_icono
from sincal.runtime import ruta_recurso
from sincal.resources import ensure_resource_available
from sincal.ui.theme import (
    COLOR_ACENTO,
    COLOR_ACENTO_HOVER,
    COLOR_BORDE,
    COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER,
    COLOR_MOSTAZA,
    COLOR_PANEL,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    FUENTE_NORMAL,
    FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO,
)

KMZ_MAX_BYTES = 10 * 1024 * 1024
KML_MAX_BYTES = 5 * 1024 * 1024
ZIP_MAX_FILES = 1000
KMZ_MAX_POINTS = 10000


def _normalizar_etiquetas(root):
    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
    return root


def _elegir_kml(zip_file):
    infos = zip_file.infolist()
    if len(infos) > ZIP_MAX_FILES:
        raise ValueError("El KMZ contiene demasiados archivos.")

    candidatos = [info for info in infos if info.filename.lower().endswith('.kml')]
    if not candidatos:
        raise ValueError("El KMZ no contiene ningún archivo KML.")

    for candidato in candidatos:
        normalizado = candidato.filename.replace('\\', '/').lower().lstrip('./')
        if normalizado == 'doc.kml':
            return candidato

    if len(candidatos) > 1:
        raise ValueError("El KMZ contiene múltiples KML y no se puede determinar cuál usar.")
    return candidatos[0]


def _leer_kml_desde_kmz(ruta_kmz):
    if os.path.getsize(ruta_kmz) > KMZ_MAX_BYTES:
        raise ValueError("El archivo KMZ es demasiado grande.")

    with zipfile.ZipFile(ruta_kmz, 'r') as zip_file:
        kml_info = _elegir_kml(zip_file)
        if kml_info.file_size > KML_MAX_BYTES:
            raise ValueError("El archivo KML interno es demasiado grande.")
        with zip_file.open(kml_info) as archivo_kml:
            return archivo_kml.read(), kml_info.filename


def _duplicado_resuelto(nombre, usados):
    if nombre not in usados:
        usados[nombre] = 1
        return nombre
    usados[nombre] += 1
    return f"{nombre} ({usados[nombre]})"


def _parsear_kml_puntos(kml_data):
    root = _normalizar_etiquetas(ET.fromstring(kml_data))
    estructuras = {}
    duplicados = {}
    ignorados = 0

    for placemark in root.findall('.//Placemark'):
        point_elem = placemark.find('Point')
        if point_elem is None:
            continue

        name_elem = placemark.find('name')
        coord_elem = placemark.find('.//coordinates')
        if name_elem is None or coord_elem is None:
            ignorados += 1
            continue

        nombre = (name_elem.text or '').strip()
        coordenadas = (coord_elem.text or '').strip()
        if not nombre or not coordenadas:
            ignorados += 1
            continue

        partes = [p.strip() for p in coordenadas.split(',')]
        if len(partes) < 2:
            ignorados += 1
            continue

        try:
            lon = float(partes[0])
            lat = float(partes[1])
        except ValueError:
            ignorados += 1
            continue

        if not (math.isfinite(lon) and math.isfinite(lat)):
            ignorados += 1
            continue
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            ignorados += 1
            continue

        nombre_final = _duplicado_resuelto(nombre, duplicados)
        estructuras[nombre_final] = (lat, lon)
        if len(estructuras) > KMZ_MAX_POINTS:
            raise ValueError("El KMZ contiene demasiados puntos válidos.")

    return estructuras, ignorados


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
        ruta_json = ruta_recurso("mapas", "mapas_calibrados.json")
        if os.path.exists(ruta_json):
            try:
                with open(ruta_json, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                self.datos_mapas = {
                    nombre: cfg for nombre, cfg in datos.items()
                    if self.mapa_esta_calibrado(cfg)
                }
                mapas_invalidos = sorted(set(datos) - set(self.datos_mapas))
                if mapas_invalidos:
                    self.parent_app.log(
                        "[!] Mapas deshabilitados por calibración inválida: " + ", ".join(mapas_invalidos)
                    )
            except Exception as e:
                self.parent_app.log(
                    f"[X] Error leyendo mapas_calibrados.json: {e}")

    def recargar_recursos(self):
        self.datos_mapas = {}
        self.cargar_bd_mapas()
        if not hasattr(self, "combo_mapas"):
            return
        lista_mapas = list(self.datos_mapas) if self.datos_mapas else [
            "No hay mapas calibrados válidos"
        ]
        self.combo_mapas.configure(
            values=lista_mapas,
            state="normal" if self.datos_mapas else "disabled",
        )
        self.combo_mapas.set(
            "Seleccione Mapa Base..." if self.datos_mapas else lista_mapas[0]
        )

    @staticmethod
    def mapa_esta_calibrado(datos_calibracion):
        try:
            lat1_geo, lon1_geo = datos_calibracion["pt1_geo"]
            x1_px, y1_px = datos_calibracion["pt1_pixel"]
            lat2_geo, lon2_geo = datos_calibracion["pt2_geo"]
            x2_px, y2_px = datos_calibracion["pt2_pixel"]
        except (KeyError, TypeError, ValueError):
            return False

        return all(
            delta != 0 for delta in (
                lon2_geo - lon1_geo,
                lat2_geo - lat1_geo,
                x2_px - x1_px,
                y2_px - y1_px,
            )
        )

    def setup_ui(self):
        fuente_subtitulo = FUENTE_SUBTITULO
        fuente_normal = FUENTE_NORMAL

        # --- 1. Panel Superior: Carga de Datos KMZ ---
        frame_top = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        frame_top.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frame_top, text="CROQUIS DE UBICACIÓN GEOGRÁFICA",
                     font=fuente_subtitulo, text_color=COLOR_MOSTAZA).pack(side="left", padx=15, pady=15)

        self.btn_cargar_kmz = ctk.CTkButton(frame_top, text="Cargar KMZ", font=fuente_normal,
                                            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0, command=self.cargar_kmz)
        self.btn_cargar_kmz.pack(side="right", padx=15, pady=15)
        ctk.CTkButton(frame_top, text="Limpiar ruta", font=FUENTE_NORMAL_PEQUENA,
                      fg_color="transparent", hover_color=COLOR_GRIS_BOTON,
                      text_color=COLOR_TEXTO_SUAVE, corner_radius=0,
                      command=self.limpiar_kmz).pack(side="right", padx=(0, 6), pady=15)

        self.lbl_kmz_status = ctk.CTkLabel(
            frame_top, text="KMZ: No cargado", font=fuente_normal, text_color=COLOR_TEXTO_SUAVE)
        self.lbl_kmz_status.pack(side="right", padx=(15, 0), pady=15)

        # --- 2. Panel Central: Selección Automatizada ---
        frame_main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        frame_main.pack(fill="both", expand=True, padx=20, pady=5)

        # A. Selector de Estructura (KMZ)
        ctk.CTkLabel(frame_main, text="1. Seleccionar Enlace (desde KMZ):", font=fuente_normal,
                     text_color=COLOR_ACENTO).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        self.combo_estructuras = ctk.CTkComboBox(frame_main, font=fuente_normal, width=400, values=[
                                                 "Cargue un archivo KMZ..."], state="disabled", command=self.actualizar_coordenadas_ui)
        self.combo_estructuras.grid(
            row=0, column=1, columnspan=3, sticky="w", padx=10, pady=(20, 10))

        ctk.CTkLabel(frame_main, text="Latitud GPS:", font=fuente_normal).grid(
            row=1, column=0, sticky="w", padx=20, pady=5)
        self.lbl_lat_val = ctk.CTkLabel(
            frame_main, text="---", font=fuente_normal, text_color=COLOR_TEXTO)
        self.lbl_lat_val.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(frame_main, text="Longitud GPS:", font=fuente_normal).grid(
            row=1, column=2, sticky="w", padx=20, pady=5)
        self.lbl_lon_val = ctk.CTkLabel(
            frame_main, text="---", font=fuente_normal, text_color=COLOR_TEXTO)
        self.lbl_lon_val.grid(row=1, column=3, sticky="w", padx=10, pady=5)

        # B. Selector de Mapa Calibrado (JSON)
        ctk.CTkLabel(frame_main, text="2. Seleccionar Mapa Base MOP:", font=fuente_normal,
                     text_color=COLOR_ACENTO).grid(row=2, column=0, sticky="w", padx=20, pady=(25, 10))

        lista_mapas = list(self.datos_mapas.keys()) if self.datos_mapas else [
            "No hay mapas calibrados válidos"]
        self.combo_mapas = ctk.CTkComboBox(
            frame_main, font=fuente_normal, width=400, values=lista_mapas)
        self.combo_mapas.grid(row=2, column=1, columnspan=3,
                              sticky="w", padx=10, pady=(25, 10))
        if not self.datos_mapas:
            self.combo_mapas.configure(state="disabled")

        # --- NUEVO: C. Controles de Micro-Ajuste Manual ---
        ctk.CTkLabel(frame_main, text="3. Micro-Ajuste en Píxeles (Opcional):", font=fuente_normal,
                     text_color=COLOR_ACENTO).grid(row=3, column=0, sticky="w", padx=20, pady=(15, 5))

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
        self.btn_generar_croquis = ctk.CTkButton(self, text="GENERAR CROQUIS DE UBICACIÓN", image=obtener_icono("pin", 19), compound="left", font=fuente_subtitulo, fg_color=COLOR_ACENTO,
                                                 hover_color=COLOR_ACENTO_HOVER, text_color="#FFFFFF", corner_radius=0, height=45, command=self.generar_croquis_png)
        self.btn_generar_croquis.pack(fill="x", padx=20, pady=(10, 20))

    def cargar_kmz(self):
        # Obtenemos la ventana madre real para evitar crasheos silenciosos de Tkinter
        ventana_principal = self.winfo_toplevel()

        ruta_kmz = filedialog.askopenfilename(
            parent=ventana_principal,
            title="Seleccionar Archivo KMZ de Google Earth", filetypes=[("Google Earth KMZ", "*.kmz")])
        if not ruta_kmz:
            return

        try:
            kml_data, kml_name = _leer_kml_desde_kmz(ruta_kmz)
            nuevas_estructuras, ignorados = _parsear_kml_puntos(kml_data)

            if nuevas_estructuras:
                self.estructuras_gps = nuevas_estructuras
                lista_nombres = sorted(list(nuevas_estructuras.keys()))
                self.combo_estructuras.configure(
                    values=lista_nombres, state="normal")
                self.combo_estructuras.set(lista_nombres[0])
                self.actualizar_coordenadas_ui(lista_nombres[0])

                self.lbl_kmz_status.configure(
                    text=f"KMZ: {os.path.basename(ruta_kmz)}", text_color=COLOR_ACENTO)
                if ignorados:
                    self.parent_app.log(
                        f"[!] KMZ cargado desde {kml_name}. Se ignoraron {ignorados} puntos inválidos.")
            else:
                messagebox.showwarning(
                    "KMZ Vacío", "No se encontraron puntos en el KMZ.", parent=ventana_principal)
        except Exception as e:
            # Enviamos el error a la consola principal de SINCAL por seguridad
            try:
                self.parent_app.log(f"[X] Error en KMZ: {str(e)}")
            except:
                pass
            messagebox.showerror(
                "Error KMZ", f"Fallo al procesar:\n{e}", parent=ventana_principal)

    def limpiar_kmz(self):
        self.estructuras_gps = {}
        self.combo_estructuras.configure(values=["Cargue un archivo KMZ..."], state="disabled")
        self.combo_estructuras.set("Cargue un archivo KMZ...")
        self.lbl_kmz_status.configure(text="KMZ: No cargado", text_color=COLOR_TEXTO_SUAVE)
        self.lbl_lat_val.configure(text="---")
        self.lbl_lon_val.configure(text="---")

    def actualizar_coordenadas_ui(self, nombre_seleccionado):
        if nombre_seleccionado in self.estructuras_gps:
            lat, lon = self.estructuras_gps[nombre_seleccionado]
            self.lbl_lat_val.configure(text=f"{lat:.6f}°")
            self.lbl_lon_val.configure(text=f"{lon:.6f}°")

            if self.datos_mapas:
                self.combo_mapas.set("Seleccione Mapa Base...")

    def generar_croquis_png(self):
        try:
            # Ventana madre absoluta para que los pop-ups no se oculten
            ventana_principal = self.winfo_toplevel()

            nombre_sel = self.combo_estructuras.get()
            mapa_sel = self.combo_mapas.get()

            if nombre_sel not in self.estructuras_gps:
                messagebox.showerror(
                    "Error", "Seleccione un enlace válido desde el KMZ.", parent=ventana_principal)
                return

            if mapa_sel not in self.datos_mapas:
                messagebox.showerror(
                    "Error", "Seleccione un Mapa Base válido de la lista desplegable.", parent=ventana_principal)
                return

            datos_calibracion = self.datos_mapas[mapa_sel]
            if not self.mapa_esta_calibrado(datos_calibracion):
                messagebox.showerror(
                    "Mapa inválido",
                    "El mapa seleccionado no tiene una calibración válida.",
                    parent=ventana_principal,
                )
                return

            ruta_mapa_base = ruta_recurso("mapas", datos_calibracion["archivo"])

            if not os.path.exists(ruta_mapa_base):
                if not messagebox.askyesno(
                    "Descargar mapa regional",
                    "La imagen de esta región todavía no está en el equipo.\n\n"
                    "¿Deseas descargarla ahora desde el canal oficial de SINCAL?",
                    parent=ventana_principal,
                ):
                    return
                relativa = f"mapas/{datos_calibracion['archivo']}"
                self.btn_generar_croquis.configure(
                    state="disabled", text="Descargando mapa regional..."
                )
                threading.Thread(
                    target=self._hilo_descargar_mapa,
                    args=(relativa,),
                    daemon=True,
                ).start()
                return

            nombre_limpio = "".join(
                c for c in nombre_sel if c.isalnum() or c in (' ', '_', '-')).rstrip()
            nombre_sugerido = f"Ubicacion_{nombre_limpio}.png"

            ruta_salida = filedialog.asksaveasfilename(
                parent=ventana_principal,
                title="Guardar Croquis de Ubicación",
                initialfile=nombre_sugerido,
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")]
            )

            if not ruta_salida:
                return

            lat1_geo, lon1_geo = datos_calibracion["pt1_geo"]
            x1_px, y1_px = datos_calibracion["pt1_pixel"]
            lat2_geo, lon2_geo = datos_calibracion["pt2_geo"]
            x2_px, y2_px = datos_calibracion["pt2_pixel"]

            try:
                gui_ajuste_x = float(self.ent_ajuste_x.get())
                gui_ajuste_y = float(self.ent_ajuste_y.get())
            except ValueError:
                gui_ajuste_x = 0
                gui_ajuste_y = 0

            ajuste_x = datos_calibracion.get("ajuste_x", 0) + gui_ajuste_x
            ajuste_y = datos_calibracion.get("ajuste_y", 0) + gui_ajuste_y

            lat_target, lon_target = self.estructuras_gps[nombre_sel]

            escala_x = (x2_px - x1_px) / (lon2_geo - lon1_geo)
            x_final = x1_px + (lon_target - lon1_geo) * escala_x + ajuste_x

            escala_y = (y2_px - y1_px) / (lat2_geo - lat1_geo)
            y_final = y1_px + (lat_target - lat1_geo) * escala_y + ajuste_y

            with Image.open(ruta_mapa_base) as img:
                img_rgba = img.convert("RGB")
                ancho, alto = img_rgba.size
                if not (0 <= x_final < ancho and 0 <= y_final < alto):
                    messagebox.showerror(
                        "Coordenada fuera de rango",
                        "La ubicación calculada cae fuera de los límites del mapa seleccionado.",
                        parent=ventana_principal,
                    )
                    return
                from PIL import ImageDraw
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
                "Workbench", f"Croquis guardado correctamente en:\n{ruta_salida}", parent=ventana_principal)

            # Uso limpio de la variable global os:
            os.startfile(os.path.dirname(ruta_salida))

        except Exception as e:
            try:
                self.parent_app.log(
                    f"[X] Error crítico en módulo croquis: {str(e)}")
            except:
                pass

            ventana = self.winfo_toplevel()
            messagebox.showerror(
                "Error", f"Ocurrió un error inesperado al procesar:\n{str(e)}", parent=ventana)

    def _hilo_descargar_mapa(self, relativa):
        try:
            ensure_resource_available(relativa)
            self.parent_app.log(f"[OK] Mapa regional descargado: {relativa}")
            self.parent_app._ui(self._mapa_descargado)
        except Exception as e:
            self.parent_app.log(f"[X] No se pudo descargar {relativa}: {e}")
            self.parent_app._ui(self._mapa_descarga_fallida, str(e))

    def _mapa_descargado(self):
        self.btn_generar_croquis.configure(
            state="normal", text="GENERAR CROQUIS DE UBICACIÓN"
        )
        self.generar_croquis_png()

    def _mapa_descarga_fallida(self, detalle):
        self.btn_generar_croquis.configure(
            state="normal", text="GENERAR CROQUIS DE UBICACIÓN"
        )
        messagebox.showerror(
            "Descarga incompleta",
            "No fue posible descargar el mapa regional.\n\n" + detalle,
            parent=self.winfo_toplevel(),
        )
