import types
import unittest
from unittest.mock import Mock, patch

import main
import sincal


class StartupTests(unittest.TestCase):
    def test_starts_core_without_blocking_on_downloadable_resources(self):
        fake_core = types.ModuleType("sincal.app")
        fake_core.arrancar = Mock()

        with (
            patch.dict("sys.modules", {"sincal.app": fake_core}),
            patch.object(sincal, "app", fake_core, create=True),
            patch.object(main, "asegurar_directorios"),
            patch.object(main.importlib, "reload", side_effect=lambda module: module),
            patch.object(main, "mostrar_error_critico") as show_error,
        ):
            main.iniciar()

        fake_core.arrancar.assert_called_once_with()
        show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
