"""Manual native UI check; all module operations and dialogs are mocked."""
from pathlib import Path
import queue
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
from sincal.ui.tabs.pasarela import TabPasarela


def main():
    root = ctk.CTk()
    root.withdraw()
    pending = queue.Queue()
    host = SimpleNamespace(_ui=lambda fn, *args: pending.put((fn, args)))
    status = {"installed": False, "source": None, "running": False,
              "version": None, "freecad_available": False, "message": "Sin instalar.",
              "online_install_available": True, "release_url": "https://github.com/drossull/sincal-updates/releases/tag/v3.0.25",
              "install_message": "Instala la versión compatible con SINCAL 3.0.25."}
    calls = []
    menu_states = []

    def backend(name, *args):
        calls.append(name)
        if name == "pasarela_status":
            return dict(status)
        if name in ("install_pasarela_package", "install_pasarela_online"):
            if name == "install_pasarela_package":
                assert Path(args[0]).suffix == ".zip"
            status.update(installed=True, source="user", version="0.3.0", message="Módulo instalado.")
            return dict(status)
        if name == "launch_pasarela":
            status["running"] = True
            return {"message": "Editor abierto."}
        if name == "close_pasarela":
            status["running"] = False
            return {"running": False}
        raise AssertionError(name)

    def settle():
        deadline = time.monotonic() + 5
        while tab._running and time.monotonic() < deadline:
            root.update()
            try:
                fn, args = pending.get(timeout=0.05)
            except queue.Empty:
                continue
            fn(*args)
        assert not tab._running, "El controlador no completó su operación."

    try:
        tab = TabPasarela(root, host, on_status=lambda value: menu_states.append(value["installed"]))
        tab._backend = backend
        tab.refresh()
        settle()
        assert tab.open_button.cget("state") == "disabled"
        assert tab.state_label.cget("text") == "Módulo no instalado"
        assert menu_states == [False]
        assert tab.online_button.cget("state") == "normal"
        assert not tab.install_panel.winfo_manager()
        with patch("sincal.ui.tabs.pasarela.webbrowser.open") as opener:
            tab.open_release()
            opener.assert_called_once_with(status["release_url"])
        tab.install_online()
        settle()
        assert menu_states[-1] is True
        assert not tab.online_button.winfo_manager()
        assert tab.open_button.winfo_manager()
        tab.toggle_manual()
        assert tab.install_panel.winfo_manager()
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "pasarela.zip"
            package.write_bytes(b"test-package")
            with patch("sincal.ui.tabs.pasarela.filedialog.askopenfilename", return_value=str(package)):
                tab.choose_package()
            assert tab.install_button.cget("state") == "normal"
            tab.install_package()
            settle()
            assert tab.open_button.cget("state") == "normal"
            assert "No detectado" in tab.details.cget("text")
            tab.open_editor()
            settle()
            assert tab.close_button.cget("state") == "normal"
            with patch("sincal.ui.tabs.pasarela.filedialog.askopenfilename", return_value=str(package)):
                tab.choose_package()
            assert tab.install_button.cget("state") == "disabled"
            with patch("sincal.ui.tabs.pasarela.messagebox.askokcancel", return_value=False):
                tab.close_editor()
            assert "close_pasarela" not in calls
            with patch("sincal.ui.tabs.pasarela.messagebox.askokcancel", return_value=True):
                tab.close_editor()
            settle()
            assert tab.install_button.cget("state") == "normal"
            assert tab.close_button.cget("state") == "disabled"
        assert "pasarela_bim" not in sys.modules
        print("OK: Tk online install, menu callback, secondary ZIP, source link, external open, save/close and update gate without editor import.")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
