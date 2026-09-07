"""Prospecciones del proyecto: tablas oficiales y envío vectorial al CAD activo."""

from __future__ import annotations

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import uuid

import customtkinter as ctk
import ttkbootstrap as ttk

from sincal.cad.prospecciones import COLORS, build_profile_lisp, lisp_string, profile_scene
from sincal.prospecciones import VsReport, read_report
from sincal.runtime import ruta_runtime
from sincal.ui.scroll import SafeScrollableFrame
from sincal.ui.theme import (
    COLOR_FONDO, COLOR_GRIS_BOTON, COLOR_GRIS_BOTON_HOVER,
    COLOR_MOSTAZA, COLOR_TEXTO_SUAVE, FUENTE_NORMAL, FUENTE_NORMAL_PEQUENA, FUENTE_SUBTITULO,
)
from sincal.ui.widgets import ShadowButton


class TabProspecciones(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.report = None
        self._generation = 0
        self._results = queue.Queue()
        self._restoring = False
        self._selected_key = ''
        self.include_table = tk.BooleanVar(value=True)
        self._build_ui()
        self.after(150, self._poll)

    def _button(self, parent, text, command):
        button = ShadowButton(
            parent, text=text, command=command, font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0)
        button.pack(side='left', padx=(0, 8), pady=4)
        return button

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(14, 8))
        ctk.CTkLabel(header, text='PROSPECCIONES', font=FUENTE_SUBTITULO,
                     text_color=COLOR_MOSTAZA).pack(anchor='w')
        ctk.CTkLabel(header, text='Perfiles Vs del informe de mecánica de suelos · Valores oficiales de solo lectura',
                     font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE).pack(anchor='w')
        actions = ctk.CTkFrame(header, fg_color='transparent')
        actions.pack(fill='x')
        self.load_button = self._button(actions, 'Cargar informe', self.choose_report)
        self._button(actions, 'Abrir sesión', lambda: self.parent_app.seleccionar_seccion('sesiones'))
        self._button(actions, 'Guardar sesión', lambda: self.parent_app.vista_armaduras.guardar_sesion())
        self._button(actions, 'Nueva sesión', lambda: self.parent_app.vista_armaduras.nueva_sesion())
        self.status = ctk.CTkLabel(header, text='Carga un PDF con texto o un TXT con tablas Vs.',
                                   font=FUENTE_NORMAL_PEQUENA, anchor='w', wraplength=760)
        self.status.pack(fill='x')
        self.page = SafeScrollableFrame(self, fg_color=COLOR_FONDO, corner_radius=0)
        self.page.pack(fill='both', expand=True, padx=20, pady=(0, 14))
        self.anchors = {}
        source = self._panel('arreglos', 'ARREGLOS DETECTADOS')
        self.source_label = ctk.CTkLabel(source, text='Sin informe', anchor='w', justify='left', wraplength=740,
                                         font=FUENTE_NORMAL_PEQUENA)
        self.source_label.pack(fill='x')
        list_host = ctk.CTkFrame(source, fg_color='transparent')
        list_host.pack(fill='x', pady=6)
        self.profiles_table = ttk.Treeview(list_host, columns=('name', 'page', 'layers', 'vs', 'warnings'),
                                           show='headings', selectmode='browse', height=6)
        for key, title, width in [('name', 'Arreglo', 150), ('page', 'Página PDF', 90),
                                   ('layers', 'Estratos', 70), ('vs', 'Vs,30 oficial (m/s)', 145),
                                   ('warnings', 'Avisos', 65)]:
            self.profiles_table.heading(key, text=title)
            self.profiles_table.column(key, width=width, minwidth=60, stretch=True)
        self.profiles_table.pack(side='left', fill='x', expand=True)
        list_scroll = ttk.Scrollbar(list_host, orient='vertical', command=self.profiles_table.yview)
        list_scroll.pack(side='right', fill='y')
        self.profiles_table.configure(yscrollcommand=list_scroll.set)
        self.profiles_table.bind('<<TreeviewSelect>>', self._select)
        details = self._panel('tabla', 'TABLA OFICIAL Y AVISOS')
        self.selection_label = ctk.CTkLabel(details, text='', anchor='w', font=FUENTE_NORMAL)
        self.selection_label.pack(fill='x', pady=(0, 6))
        table_host = ctk.CTkFrame(details, fg_color='transparent')
        table_host.pack(fill='x')
        self.layers_table = ttk.Treeview(table_host, columns=('n', 'start', 'end', 'vs'),
                                         show='headings', height=7)
        for key, title in [('n', 'Estrato'), ('start', 'Inicio (m)'), ('end', 'Final (m)'), ('vs', 'Vs (m/s)')]:
            self.layers_table.heading(key, text=title)
            self.layers_table.column(key, width=120, minwidth=65)
        self.layers_table.pack(side='left', fill='x', expand=True)
        table_scroll = ttk.Scrollbar(table_host, orient='vertical', command=self.layers_table.yview)
        table_scroll.pack(side='right', fill='y')
        self.layers_table.configure(yscrollcommand=table_scroll.set)
        self.warning_label = ctk.CTkLabel(details, text='', justify='left', anchor='w', wraplength=740,
                                          font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_MOSTAZA)
        self.warning_label.pack(fill='x', pady=8)
        tools = ctk.CTkFrame(details, fg_color='transparent')
        tools.pack(fill='x')
        self._button(tools, 'Ver texto de origen', self.show_source)
        self._button(tools, 'Copiar avisos', self.copy_warnings)
        preview = self._panel('vista', 'VISTA PREVIA E INSERCIÓN CAD')
        controls = ctk.CTkFrame(preview, fg_color='transparent')
        controls.pack(fill='x')
        ttk.Checkbutton(controls, text='Incluir tabla en CAD', variable=self.include_table,
                         command=self._option_changed).pack(side='left', padx=(0, 12))
        self.insert_button = self._button(controls, 'Insertar en CAD', self.insert_cad)
        self.insert_button.configure(state='disabled')
        ctk.CTkLabel(preview,
                     text='Model en metros · RomanD anotativo · Texto 2,5 mm · Cuadrícula 100 × 150 mm de papel\n'
                          'Se utiliza la escala anotativa actual del CAD. Selecciona allí el punto de inserción.',
                     font=FUENTE_NORMAL_PEQUENA, justify='left', anchor='w').pack(fill='x', pady=6)
        self.canvas = tk.Canvas(preview, background='#595959', highlightthickness=0, height=780)
        self.canvas.pack(fill='x')
        self.canvas.bind('<Configure>', lambda _event: self.draw_preview())

    def _panel(self, key, title):
        host = ctk.CTkFrame(self.page, fg_color='transparent')
        host.pack(fill='x', pady=(0, 18))
        ctk.CTkLabel(host, text=title, font=FUENTE_NORMAL, text_color=COLOR_MOSTAZA).pack(anchor='w')
        self.anchors[key] = host
        return host

    def snapshot(self):
        return {'report': self.report.to_dict() if self.report else None,
                'selected_key': self._selected_key, 'include_table': self.include_table.get()}

    @staticmethod
    def validate_snapshot(data):
        if data is not None and not isinstance(data, dict):
            raise ValueError('Prospecciones no contiene un objeto válido.')
        if data and data.get('report'):
            VsReport.from_dict(data['report'])

    def restore(self, data=None):
        self.validate_snapshot(data)
        self._generation += 1  # Una lectura pendiente no debe contaminar otra sesión.
        self._restoring = True
        try:
            data = data or {}
            self.report = VsReport.from_dict(data['report']) if data.get('report') else None
            self._selected_key = str(data.get('selected_key', ''))
            self.include_table.set(bool(data.get('include_table', True)))
            self.load_button.configure(state='normal', text='Cargar informe')
            self._refresh()
        finally:
            self._restoring = False

    def choose_report(self):
        path = filedialog.askopenfilename(title='Informe de mecánica de suelos',
                                          filetypes=[('Informes PDF', '*.pdf'), ('Tablas de texto', '*.txt')])
        if not path:
            return
        if self.report and not messagebox.askyesno('Reemplazar informe',
                '¿Reemplazar el informe de esta sesión? Puedes guardar la sesión antes de continuar.'):
            return
        self._generation += 1
        token = self._generation
        self.load_button.configure(state='disabled', text='Leyendo…')
        self.status.configure(text='Buscando tablas Vs en el informe…')

        def work():
            try:
                result = read_report(path)
            except Exception as error:
                result = error
            self._results.put((token, result))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                token, result = self._results.get_nowait()
                if token != self._generation:
                    continue
                self.load_button.configure(state='normal', text='Cargar informe')
                if isinstance(result, Exception):
                    self.status.configure(text='No se pudo cargar el nuevo informe. Se conserva el estado anterior.')
                    messagebox.showerror('Prospecciones', str(result), parent=self.winfo_toplevel())
                else:
                    self.report = result
                    self._selected_key = result.profiles[0].key
                    self._refresh()
                    self._changed()
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _refresh(self):
        self.profiles_table.delete(*self.profiles_table.get_children())
        if self.report:
            self.source_label.configure(text=self.report.path)
            for p in self.report.profiles:
                self.profiles_table.insert('', 'end', iid=p.key,
                    values=(p.name, p.page, len(p.layers), p.official_vs30 or 'No identificado', len(p.warnings())))
            if self._selected_key not in [p.key for p in self.report.profiles]:
                self._selected_key = self.report.profiles[0].key if self.report.profiles else ''
            if self._selected_key:
                self.profiles_table.selection_set(self._selected_key)
                self.profiles_table.see(self._selected_key)
            self.status.configure(text=f'{len(self.report.profiles)} arreglos detectados · Valores oficiales conservados')
        else:
            self._selected_key = ''
            self.source_label.configure(text='Sin informe')
            self.status.configure(text='Carga un PDF con texto o un TXT con tablas Vs.')
        self._show_profile()

    def selected_profile(self):
        return next((p for p in self.report.profiles if p.key == self._selected_key), None) if self.report else None

    def _select(self, _event=None):
        selection = self.profiles_table.selection()
        if not selection:
            return
        changed = self._selected_key != selection[0]
        self._selected_key = selection[0]
        self._show_profile()
        if changed:
            self._changed()

    def _show_profile(self):
        self.layers_table.delete(*self.layers_table.get_children())
        profile = self.selected_profile()
        self.selection_label.configure(text=(
            f'{profile.name} · Página PDF {profile.page} · Vs,30 oficial: '
            f'{profile.official_vs30 or "No identificado"}' + (' m/s' if profile.official_vs30 else '')
            if profile else ''))
        if profile:
            for row in profile.layers:
                self.layers_table.insert('', 'end', values=(row.index, row.start, row.end, row.vs))
        notices = (self.report.notices if self.report else []) + (profile.warnings() if profile else [])
        self.warning_label.configure(text='\n'.join(notices) if notices else (
            'Sin discrepancias detectadas en los controles disponibles.' if profile else 'Selecciona un arreglo.'))
        self.insert_button.configure(state='normal' if profile and not profile.errors() else 'disabled')
        self.draw_preview()

    def _changed(self):
        if not self._restoring:
            self.parent_app.vista_armaduras.marcar_sesion_modificada()

    def _option_changed(self):
        self.draw_preview()
        self._changed()

    def draw_preview(self):
        self.canvas.delete('all')
        profile = self.selected_profile()
        if not profile or profile.errors():
            return
        scene = profile_scene(profile, self.include_table.get())
        scale = min(3.4, max(1, (self.canvas.winfo_width() - 80) / 145))
        dx, dy = 65, 25
        for item in scene:
            color = COLORS[item['color']]
            if item['kind'] in ('line', 'polyline'):
                pts = [coordinate for x, y in item['points'] for coordinate in (dx + x * scale, dy + y * scale)]
                self.canvas.create_line(*pts, fill=color, width=1.3 if item['color'] == 5 else 1)
            else:
                x, y = item['point']
                x, y = dx + x * scale, dy + y * scale
                if item['kind'] == 'circle':
                    r = item['radius'] * scale
                    self.canvas.create_oval(x-r, y-r, x+r, y+r, outline=color)
                else:
                    anchor = {'left': 'w', 'right': 'e', 'center': 'center'}[item['anchor']]
                    self.canvas.create_text(x, y, text=item['text'], fill=color, anchor=anchor,
                                             font=('Arial', max(7, round(2.5 * scale)), 'normal'))
        bounds = self.canvas.bbox('all')
        if bounds:
            self.canvas.configure(height=bounds[3] + 20)

    def show_source(self):
        profile = self.selected_profile()
        if not profile:
            return
        window = ctk.CTkToplevel(self)
        window.title(f'{profile.name} · Página PDF {profile.page}')
        window.geometry('850x650')
        box = ctk.CTkTextbox(window, wrap='word')
        box.pack(fill='both', expand=True, padx=12, pady=12)
        box.insert('1.0', profile.source_text)
        box.configure(state='disabled')

    def copy_warnings(self):
        if not self.report:
            return
        lines = [f'Informe: {self.report.path}', f'SHA-256: {self.report.sha256}']
        lines.extend(self.report.notices)
        for profile in self.report.profiles:
            lines.extend(f'{profile.name} (p. {profile.page}): {w}' for w in profile.warnings())
        self.clipboard_clear()
        self.clipboard_append('\n'.join(lines))
        self.status.configure(text='Avisos y referencia del informe copiados.')

    def insert_cad(self):
        profile = self.selected_profile()
        if not profile:
            return
        try:
            content = build_profile_lisp(profile, self.include_table.get())
            path = Path(ruta_runtime(f'SINCAL_VS_{uuid.uuid4().hex}.lsp'))
            path.write_text(content, encoding='utf-8')
        except (OSError, ValueError) as error:
            messagebox.showerror('Prospecciones', str(error), parent=self.winfo_toplevel())
            return
        self.parent_app.enviar_comando_cad_activo(
            f'(progn (load {lisp_string(path.as_posix())}) (c:SINCAL-PROSPECCIONES))\n',
            f'Prospecciones · {profile.name}')
        self.status.configure(text='Solicitud enviada. Revisa la consola del CAD y selecciona el punto de inserción.')

    def ir_a_seccion(self, anchor):
        if anchor in self.anchors:
            self.page.update_idletasks()
            y = self.anchors[anchor].winfo_y()
            self.page._parent_canvas.yview_moveto(y / max(1, self.page.winfo_reqheight()))
