"""El guardado del proyecto conserva archivos, permisos de sesión y borradores."""

import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from pasarela_bim.archivos import FileBusy, FileConflict, ProjectFiles, _windows_dialog


def draft(name="Pasarela Los Batros"):
    return {"version": 2, "proyecto": {"nombre": name, "unidades": "m", "estado": "borrador"},
            "nodos": [], "tramos": [], "familias": {}, "soportes": [], "fundaciones": []}


class TestProjectFiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "Pasarela Ñuble revisión.json"
        self.select_open = Mock(return_value=self.path)
        self.select_save = Mock(return_value=self.path)
        self.files = ProjectFiles(select_open=self.select_open, select_save=self.select_save)

    def write(self, model=None):
        raw = json.dumps(model or draft(), ensure_ascii=False).encode("utf-8")
        self.path.write_bytes(raw)
        return raw

    def test_first_save_then_overwrite_keeps_token_and_prompts_once(self):
        first = self.files.save_project({"modelo": draft(), "nombre_sugerido": "Los Batros.json"})
        token = first["documento"]["id"]
        model = draft("Modificado")
        result = self.files.save_project({"modelo": model, "documento_id": token})
        self.assertEqual(result["documento"], first["documento"])
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), model)
        self.select_save.assert_called_once_with("Los Batros.json")
        self.select_open.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_open_legacy_and_save_converts_to_meters_and_preserves_metadata(self):
        legacy = draft()
        legacy.update(version=1, nodos=[{"id": "A", "x": 1000, "y": 2000, "z": 3000}])
        legacy["proyecto"].update(unidades="mm", referencia={"ptl": "proyecto"})
        raw = self.write(legacy)
        opened = self.files.open_project()
        self.assertEqual(opened["modelo"]["nodos"][0]["x"], 1)
        self.assertEqual(self.path.read_bytes(), raw)
        result = self.files.save_project({"modelo": opened["modelo"], "documento_id": opened["documento"]["id"]})
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["version"], 2)
        self.assertEqual(stored["proyecto"]["referencia"], {"ptl": "proyecto"})
        self.assertEqual(result["documento"], opened["documento"])
        self.select_save.assert_not_called()

    def test_cancel_open_and_first_save_creates_no_document(self):
        self.select_open.return_value = None
        self.select_save.return_value = None
        self.assertEqual(self.files.open_project(), {"cancelado": True})
        self.assertEqual(self.files.save_project({"modelo": draft()}), {"cancelado": True})
        self.assertFalse(self.files._documents)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_save_as_cancel_and_failure_keep_original_association(self):
        raw = self.write()
        token = self.files.open_project()["documento"]["id"]
        self.select_save.return_value = None
        args = {"modelo": draft("Cambios"), "documento_id": token, "guardar_como": True}
        self.assertEqual(self.files.save_project(args), {"cancelado": True})
        self.select_save.return_value = self.root / "copia.json"
        with patch("pasarela_bim.archivos.os.replace", side_effect=PermissionError("bloqueado")):
            with self.assertRaises(PermissionError):
                self.files.save_project(args)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(list(self.files._documents), [token])
        self.assertEqual(list(self.root.iterdir()), [self.path])
        args.pop("guardar_como")
        self.files.save_project(args)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["proyecto"]["nombre"], "Cambios")

    def test_save_as_success_uses_new_association_and_keeps_original(self):
        raw = self.write()
        original = self.files.open_project()["documento"]
        copy_path = self.root / "Otra pasarela.json"
        self.select_save.return_value = copy_path
        result = self.files.save_project({"modelo": draft("Copia"), "documento_id": original["id"], "guardar_como": True})
        self.assertNotEqual(result["documento"]["id"], original["id"])
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(json.loads(copy_path.read_text(encoding="utf-8"))["proyecto"]["nombre"], "Copia")

    def test_replace_failure_keeps_original_and_retry_is_possible(self):
        raw = self.write()
        opened = self.files.open_project()
        args = {"modelo": draft("Nuevo"), "documento_id": opened["documento"]["id"]}
        with patch("pasarela_bim.archivos.os.replace", side_effect=OSError("disco")):
            with self.assertRaises(OSError):
                self.files.save_project(args)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(list(self.root.iterdir()), [self.path])
        self.assertTrue(self.files.save_project(args)["guardado"])

    def test_flush_failure_keeps_original_and_cleans_temporary_file(self):
        raw = self.write()
        opened = self.files.open_project()
        with patch("pasarela_bim.archivos.os.fsync", side_effect=OSError("sin espacio")):
            with self.assertRaises(OSError):
                self.files.save_project({"modelo": draft("Nuevo"), "documento_id": opened["documento"]["id"]})
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_conflict_on_external_edit_and_delete(self):
        self.write()
        token = self.files.open_project()["documento"]["id"]
        external = self.write(draft("Colega"))
        args = {"modelo": draft("Mi cambio"), "documento_id": token}
        with self.assertRaises(FileConflict):
            self.files.save_project(args)
        self.assertEqual(self.path.read_bytes(), external)
        self.path.unlink()
        with self.assertRaises(FileConflict):
            self.files.save_project(args)
        self.assertFalse(self.path.exists())
        self.select_save.assert_not_called()

    def test_conflict_during_atomic_write_is_detected(self):
        self.write()
        token = self.files.open_project()["documento"]["id"]
        external = json.dumps(draft("Otro usuario")).encode()
        with patch("pasarela_bim.archivos.os.fsync", side_effect=lambda fd: self.path.write_bytes(external)):
            with self.assertRaises(FileConflict):
                self.files.save_project({"modelo": draft("Mi cambio"), "documento_id": token})
        self.assertEqual(self.path.read_bytes(), external)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_cannot_supply_a_path_or_use_token_from_another_session(self):
        for extra in ({"ruta": str(self.path)}, {"path": str(self.path)},
                      {"documento_id": str(self.path)}, {"documento_id": []}, {"guardar_como": "sí"},
                      {"nombre_sugerido": 0}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.files.save_project({"modelo": draft(), **extra})
        token = self.files.save_project({"modelo": draft()})["documento"]["id"]
        other = ProjectFiles(select_open=self.select_open, select_save=self.select_save)
        with self.assertRaises(ValueError):
            other.save_project({"modelo": draft(), "documento_id": token})
        self.select_save.assert_called_once()

    def test_filename_suggestion_never_selects_a_directory(self):
        self.files.save_project({"modelo": draft(), "nombre_sugerido": r"C:\No autorizado\..\válido.json"})
        self.select_save.assert_called_once_with("válido.json")

    def test_malformed_json_version_units_and_nonfinite_numbers(self):
        malformed = [b"no json", b"[]", b"{}", b'{"version":2,"proyecto":{"unidades":"m"},"x":NaN}',
                     b'{"version":2,"proyecto":{"unidades":"mm"}}', b"\xff"]
        for raw in malformed:
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.files.open_project()
        bad_models = [None, [], {}, {"version": True, "proyecto": {"unidades": "mm"}},
                      {**draft(), "invalid": float("inf")}]
        for model in bad_models:
            with self.subTest(model=model), self.assertRaises(ValueError):
                self.files.save_project({"modelo": model})
        self.assertFalse(self.files._documents)
        self.select_save.assert_not_called()

    def test_size_limit_on_read_and_write(self):
        model = copy.deepcopy(draft())
        model["notas"] = "a" * 300
        self.write(model)
        with patch("pasarela_bim.archivos.MAX_PROJECT_BYTES", 256):
            with self.assertRaisesRegex(ValueError, "20 MiB"):
                self.files.open_project()
            with self.assertRaisesRegex(ValueError, "20 MiB"):
                self.files.save_project({"modelo": model})
        self.select_save.assert_not_called()

    def test_concurrent_operations_do_not_open_second_dialog(self):
        entered, release = threading.Event(), threading.Event()
        def choose():
            entered.set()
            release.wait(2)
            return None
        self.select_open.side_effect = choose
        worker = threading.Thread(target=self.files.open_project)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(FileBusy):
                self.files.save_project({"modelo": draft()})
            self.select_save.assert_not_called()
        finally:
            release.set()
            worker.join(2)

    @unittest.skipUnless(os.name == "nt", "Contrato de los selectores Win32")
    def test_native_selector_unicode_and_overwrite_confirmation_without_showing_ui(self):
        import ctypes
        selected = str(self.path)
        seen = []
        def choose(pointer):
            params = pointer._obj
            seen.append((params.Flags, params.nMaxFile, params.lpstrFile, params.lpstrDefExt))
            address = ctypes.c_void_p.from_address(ctypes.addressof(params) + type(params).lpstrFile.offset).value
            text = ctypes.create_unicode_buffer(selected)
            ctypes.memmove(address, text, ctypes.sizeof(text))
            return 1
        api = SimpleNamespace(GetOpenFileNameW=Mock(side_effect=choose), GetSaveFileNameW=Mock(side_effect=choose),
                              CommDlgExtendedError=Mock(return_value=0))
        user = SimpleNamespace(GetForegroundWindow=Mock(return_value=None))
        with patch("ctypes.WinDLL", side_effect=[api, user, api, user]):
            self.assertEqual(_windows_dialog(save=True, suggested="Proyecto Ñuble.json"), self.path)
            self.assertEqual(_windows_dialog(), self.path)
        self.assertTrue(seen[0][0] & 0x2, "Windows debe confirmar al reemplazar archivos existentes")
        self.assertTrue(seen[1][0] & 0x1000, "Abrir debe exigir un archivo existente")
        self.assertEqual(seen[0][1:], (32768, "Proyecto Ñuble.json", "json"))

    @unittest.skipUnless(os.name == "nt", "Contrato de los selectores Win32")
    def test_native_selector_cancel_and_failure_without_showing_ui(self):
        api = SimpleNamespace(GetSaveFileNameW=Mock(return_value=0), CommDlgExtendedError=Mock(side_effect=[0, 1]))
        user = SimpleNamespace(GetForegroundWindow=Mock(return_value=None))
        with patch("ctypes.WinDLL", side_effect=[api, user, api, user]):
            self.assertIsNone(_windows_dialog(save=True))
            with self.assertRaises(OSError):
                _windows_dialog(save=True)


if __name__ == "__main__":
    unittest.main()
