import types
import unittest
from unittest.mock import Mock, patch

from sincal import app as core_sincal
from sincal.resources import ResourceSyncResult, ResourceUpdatePlan


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
        plan = ResourceUpdatePlan("a" * 40, (), (), (), False)

        with (
            patch.object(core_sincal, "check_resource_updates", return_value=plan),
            patch.object(core_sincal, "apply_resource_updates", return_value=result),
            patch.object(core_sincal, "record_incident"),
        ):
            core_sincal.ActualizadorCAD._hilo_aplicar_recursos(app, plan)

        messages = [call.args[0] for call in app.log.call_args_list]
        self.assertTrue(any("[OK] Actualización menor instalada" in message for message in messages))
        callbacks = [call.args[0] for call in app._ui.call_args_list]
        self.assertIn(core_sincal.messagebox.showwarning, callbacks)
        self.assertNotIn(core_sincal.messagebox.showerror, callbacks)

    def test_failed_cad_activation_allows_future_automatic_offer(self):
        app = self._fake_app()
        app._resource_manifest_revision = "b" * 40
        app._last_resource_offer_tree = "a" * 40
        app._preparar_archivos_cad.side_effect = OSError("loader locked")
        plan = ResourceUpdatePlan("a" * 40, (), (), (), False, "b" * 40)
        result = ResourceSyncResult(("lisps/PURGEALL.lsp",), (), "a" * 40, "b" * 40)
        with (
            patch.object(core_sincal, "check_resource_updates", return_value=plan),
            patch.object(core_sincal, "apply_resource_updates", return_value=result),
            patch.object(core_sincal, "record_incident"),
        ):
            core_sincal.ActualizadorCAD._hilo_aplicar_recursos(app, plan)
        self.assertEqual(app._resource_manifest_revision, "")
        self.assertEqual(app._last_resource_offer_tree, "")
        app._recargar_lisps_cad_abierto.assert_not_called()
        callbacks = [call.args[0] for call in app._ui.call_args_list]
        self.assertIn(core_sincal.messagebox.showwarning, callbacks)
        self.assertNotIn(core_sincal.messagebox.showerror, callbacks)

    def test_rejects_obsolete_plan_before_writing_resources(self):
        app = self._fake_app()
        app._resource_manifest_revision = "c" * 40
        app._last_resource_offer_tree = "a" * 40
        selected = ResourceUpdatePlan("a" * 40, (), (), (), False, "c" * 40)
        newer = ResourceUpdatePlan("b" * 40, (), (), (), False, "d" * 40)
        with (
            patch.object(core_sincal, "check_resource_updates", return_value=newer),
            patch.object(core_sincal, "apply_resource_updates") as apply,
            patch.object(core_sincal, "record_incident"),
        ):
            core_sincal.ActualizadorCAD._hilo_aplicar_recursos(app, selected)
        apply.assert_not_called()
        app._preparar_archivos_cad.assert_not_called()
        self.assertEqual(app._resource_manifest_revision, "")
        self.assertEqual(app._last_resource_offer_tree, "")
        callbacks = [call.args[0] for call in app._ui.call_args_list]
        self.assertIn(core_sincal.messagebox.showerror, callbacks)

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

    def test_periodic_check_does_not_remember_floating_manifest_from_another_tree(self):
        app = self._fake_app()
        app._resource_manifest_revision = "a" * 40
        app._last_resource_offer_tree = ""
        app._resource_check_running = True
        old_plan = ResourceUpdatePlan("b" * 40, (), (), (), False, "c" * 40)
        new_plan = ResourceUpdatePlan("d" * 40, (), (), (), False, "e" * 40)
        with (
            patch.object(core_sincal, "distribution_manifest_revision", return_value="e" * 40),
            patch.object(core_sincal, "check_resource_updates", side_effect=[old_plan, new_plan]) as check,
            patch.object(core_sincal, "record_resource_state") as record,
            patch.object(core_sincal, "record_incident") as incident,
        ):
            core_sincal.ActualizadorCAD._hilo_verificar_recursos(
                app, manual=False, periodic=True, manifest_only=True
            )
            self.assertEqual(app._resource_manifest_revision, "c" * 40)
            # A later poll must still inspect the tree: the earlier floating
            # manifest was newer than the snapshot actually checked.
            core_sincal.ActualizadorCAD._hilo_verificar_recursos(
                app, manual=False, periodic=True, manifest_only=True
            )
            self.assertEqual(check.call_count, 2)
            self.assertEqual(app._resource_manifest_revision, "e" * 40)
            self.assertEqual(record.call_count, 2)
            incident.assert_not_called()
        self.assertFalse(app._resource_check_running)


if __name__ == "__main__":
    unittest.main()
