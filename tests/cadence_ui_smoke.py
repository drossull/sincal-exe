"""Run with python tests/cadence_ui_smoke.py; isolated state, no CAD/network."""
import os
import logging
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


def main():
    with tempfile.TemporaryDirectory(prefix='sincal-ui-smoke-', ignore_cleanup_errors=True) as temporary:
        os.environ['LOCALAPPDATA'] = temporary
        os.environ['APPDATA'] = temporary
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from sincal.app import ActualizadorCAD
        from sincal.ui.theme import COLOR_FONDO, aplicar_familia, THEME_LABELS
        from sincal.ui.preferences import load_preferences
        import customtkinter as ctk
        from tkinter import font
        errors = []
        with patch('threading.Thread.start'), patch.object(ActualizadorCAD, '_offer_last_project'), \
             patch.object(ActualizadorCAD, 'report_callback_exception', side_effect=lambda *args: errors.append(args)):
            app = ActualizadorCAD()
            try:
                print('App created', flush=True)
                app.geometry('1480x900')
                app.update()
                print('Layout ready', flush=True)
                app.vista_armaduras.ent_z_esviaje.delete(0, 'end')
                app.vista_armaduras.ent_z_esviaje.insert(0, '12.5')
                for family in THEME_LABELS:
                    for dark in (False, True):
                        aplicar_familia(app.bootstrap_style, family, dark)
                        assert app.bootstrap_style.colors.bg.lower() == COLOR_FONDO[int(dark)].lower()
                    print('Palette:', family, flush=True)
                for family, mode in [('cadence', 'Tema oscuro'), ('nord', 'Tema claro'), ('tokyo-night', 'Tema oscuro')]:
                    app.theme_family_var.set(THEME_LABELS[family])
                    app._choose_theme_family()
                    app.cambiar_tema(mode)
                    app.update()
                    assert app.sidebar.cget('fg_color') is COLOR_FONDO
                    assert app.sidebar._canvas.cget('bg').lower() == COLOR_FONDO[int(mode == 'Tema oscuro')].lower()
                    assert app.theme_selector.get() == THEME_LABELS[family]
                    assert app.vista_armaduras.ent_z_esviaje.get() == '12.5'
                app._toggle_theme_mode()
                assert app._theme_family == 'tokyo-night'
                assert app._theme_mode == 'light'
                assert load_preferences()['family'] == 'tokyo-night'
                app.seleccionar_seccion('estructural')
                app.update()
                content = app.vista_armaduras
                app._set_side_panels(False, animate=False)
                app.update()
                assert not app.sidebar.winfo_manager()
                assert not app.page_nav_column.winfo_manager()
                app._set_side_panels(True)
                app._set_side_panels(False)
                app._set_side_panels(True)
                deadline = time.monotonic() + .5
                while time.monotonic() < deadline:
                    app.update()
                    time.sleep(.01)
                assert app.sidebar.winfo_manager() == 'pack'
                assert app.page_nav_column.winfo_manager() == 'pack'
                assert app.page_nav_column.cget('width') == 260
                assert app.vista_armaduras is content
                app.cambiar_tamano_letra(1.15)
                app.update()
                actual = font.Font(root=app, font=app.bootstrap_style.lookup('TLabel', 'font')).actual()
                assert actual['slant'] == 'roman'
                assert actual['family'] == 'Roboto'
                app.geometry('1000x760')
                app.update()
                assert not app.sidebar.winfo_manager()
                assert not app.page_nav_column.winfo_manager()
                app.geometry('1480x900')
                app.update()
                assert app.sidebar.winfo_manager() == 'pack'
                assert app.page_nav_column.winfo_manager() == 'pack'
                assert not errors, errors
                print('PASS: 32 palettes, selector/mode, persistence, zoom, real widgets, responsive and interrupted transitions')
            finally:
                app._panel_transition.cancel()
                app.destroy()
                logging.shutdown()


if __name__ == '__main__':
    main()
