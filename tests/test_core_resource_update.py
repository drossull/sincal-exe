import types
import unittest
from unittest.mock import Mock, patch

import core_sincal
from sincal_resource_sync import ResourceSyncResult


class CoreResourceUpdateTests(unittest.TestCase):
    def _fake_app(self):
        return types.SimpleNamespace(
            logger=Mock(),
            log=Mock(),
            _preparar_archivos_cad=Mock(),
            _recargar_lisps_cad_abierto=Mock(),
            _refrescar_interfaces_recursos=Mock(),
            _ui=Mock(),
            btn_sync_resources=types.SimpleNamespace(configure=Mock()),
        )

    def test_cad_reload_failure_does_not_mark_download_as_failed(self):
        app = self._fake_app()
        app._recargar_lisps_cad_abierto.side_effect = RuntimeError("CAD ocupado")
        result = ResourceSyncResult(
            updated=("tutoriales.json",),
            removed=(),
            tree_sha="a" * 40,
        )

        with (
            patch.object(core_sincal, "apply_resource_updates", return_value=result),
            patch.object(core_sincal, "record_incident"),
        ):
            core_sincal.ActualizadorCAD._hilo_aplicar_recursos(app, object())

        messages = [call.args[0] for call in app.log.call_args_list]
        self.assertTrue(any("[OK] Actualización menor instalada" in message for message in messages))
        callbacks = [call.args[0] for call in app._ui.call_args_list]
        self.assertIn(core_sincal.messagebox.showwarning, callbacks)
        self.assertNotIn(core_sincal.messagebox.showerror, callbacks)

    def test_unavailable_documents_collection_is_ignored(self):
        app = types.SimpleNamespace(logger=Mock())
        documents = Mock()
        type(documents).Count = property(lambda _: (_ for _ in ()).throw(RuntimeError("CAD ocupado")))
        cad_app = types.SimpleNamespace(Documents=documents)

        with (
            patch.object(core_sincal.pythoncom, "CoInitialize"),
            patch.object(core_sincal.pythoncom, "CoUninitialize"),
            patch.object(core_sincal.win32com.client, "GetActiveObject", return_value=cad_app),
        ):
            count = core_sincal.ActualizadorCAD._recargar_lisps_cad_abierto(app)

        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
