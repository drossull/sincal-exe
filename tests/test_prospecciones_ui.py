"""Prueba del flujo de sesión con los widgets reales, sin dibujos CAD."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import customtkinter as ctk
from sincal.project import ProjectContext
from sincal.prospecciones import parse_pages
from sincal.sessions import SessionStore
from sincal.ui.tabs.armaduras import TabArmaduras
from sincal.ui.tabs.prospecciones import TabProspecciones
from sincal.ui.theme import crear_estilo_bootstrap
from test_prospecciones import PAGE


@patch('sincal.ui.tabs.armaduras.messagebox.showinfo')
def test_real_widgets_save_restore_reset_and_ignore_old_import(_showinfo, tmp_path):
    root = ctk.CTk()
    root.withdraw()
    crear_estilo_bootstrap()
    context = ProjectContext()
    app = SimpleNamespace(
        session_store=SessionStore(tmp_path, tmp_path / 'recovery'),
        configurar_navegacion_pagina=Mock(), actualizar_ruta_interna=Mock(),
        marcar_navegacion_pagina=Mock(), log_r=Mock(),
        activate_project_snapshot=Mock(), seleccionar_seccion=Mock(),
        enviar_comando_cad_activo=Mock(),
    )
    try:
        app.vista_armaduras = TabArmaduras(root, app, project_context=context)
        tab = app.vista_prospecciones = TabProspecciones(root, app)
        report = parse_pages([PAGE], path='missing.pdf', sha256='reference')
        tab.restore({'report': report.to_dict()})
        root.update_idletasks()
        assert len(tab.profiles_table.get_children()) == 1
        assert len(tab.layers_table.get_children()) == 7
        tab._option_changed()
        assert app.vista_armaduras._session_dirty
        app.vista_armaduras._session_metadata['name'] = 'Prospecciones sin JSON'
        assert app.vista_armaduras.guardar_sesion()
        path = app.vista_armaduras._session_path
        token = tab._generation
        assert app.vista_armaduras.nueva_sesion()
        assert tab.report is None
        assert not app.vista_armaduras._session_dirty
        tab._results.put((token, report))
        tab._poll()
        assert tab.report is None
        assert app.vista_armaduras.abrir_sesion_desde_ruta(path)
        assert tab.report.to_dict() == report.to_dict()
        assert not app.vista_armaduras._session_dirty
        _, legacy = app.session_store.save({'metadata': {'name': 'Old'}})
        assert app.vista_armaduras.abrir_sesion_desde_ruta(legacy)
        assert tab.report is None
        # Invalid prospect data is validated before the current session changes.
        tab.restore({'report': report.to_dict()})
        _, invalid = app.session_store.save({'prospecciones': {'report': {'profiles': [{}]}}})
        with patch('sincal.ui.tabs.armaduras.messagebox.showerror'):
            assert not app.vista_armaduras.abrir_sesion_desde_ruta(invalid)
        assert tab.report.to_dict() == report.to_dict()
    finally:
        root.destroy()
