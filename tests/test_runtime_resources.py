import json
import os
import tempfile
import unittest
from unittest.mock import patch

from sincal import runtime as sincal_runtime


class RuntimeResourceResolutionTests(unittest.TestCase):
    def test_uses_overlay_fallback_and_tombstone(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            installed = os.path.join(temp_dir, "installed")
            cache = os.path.join(temp_dir, "cache")
            os.makedirs(os.path.join(installed, "lisps"))
            os.makedirs(os.path.join(cache, "lisps"))

            installed_sincal = os.path.join(installed, "lisps", "SINCAL.lsp")
            cached_new = os.path.join(cache, "lisps", "NEW.lsp")
            with open(installed_sincal, "w", encoding="utf-8") as target:
                target.write("installed")
            with open(cached_new, "w", encoding="utf-8") as target:
                target.write("cached")
            with open(os.path.join(cache, "resource_sync.json"), "w", encoding="utf-8") as target:
                json.dump(
                    {
                        "resources": {
                            "lisps/SINCAL.lsp": {"sha": "a" * 40, "size": 9},
                            "lisps/NEW.lsp": {"sha": "b" * 40, "size": 6},
                        }
                    },
                    target,
                )

            with (
                patch.object(sincal_runtime, "RUTA_RECURSOS", installed),
                patch.object(sincal_runtime, "RUTA_RECURSOS_USUARIO", cache),
            ):
                self.assertEqual(sincal_runtime.ruta_recurso("lisps", "NEW.lsp"), cached_new)
                self.assertEqual(sincal_runtime.ruta_recurso("lisps", "SINCAL.lsp"), installed_sincal)
                self.assertEqual(
                    sincal_runtime.ruta_recurso("lisps", "REMOVED.lsp"),
                    os.path.join(cache, "lisps", "REMOVED.lsp"),
                )
                self.assertEqual(
                    sincal_runtime.ruta_recurso("assets", "icons", "logo.ico"),
                    os.path.join(installed, "assets", "icons", "logo.ico"),
                )


if __name__ == "__main__":
    unittest.main()
