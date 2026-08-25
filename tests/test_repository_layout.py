import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_application_code_is_grouped_by_responsibility(self):
        required = (
            "sincal/app.py",
            "sincal/cad/engine.py",
            "sincal/cad/zapata_views.py",
            "sincal/rebar/model.py",
            "sincal/rebar/detail.py",
            "sincal/ui/theme.py",
            "sincal/ui/tabs/armaduras.py",
            "packaging/windows/SINCAL.spec",
            "packaging/windows/SINCAL_Installer.iss",
            "assets/icons/logo.ico",
        )
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_legacy_root_modules_are_not_reintroduced(self):
        legacy = (
            "core_sincal.py",
            "sincal_runtime.py",
            "sincal_resource_sync.py",
            "sincal_ui.py",
            "sincal_zapata_cad.py",
            "SINCAL.spec",
            "SINCAL_Installer.iss",
            "logo.ico",
        )
        for relative in legacy:
            self.assertFalse((ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()

