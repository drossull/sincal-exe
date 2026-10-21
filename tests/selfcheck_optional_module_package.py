"""Install and launch a built optional ZIP through the real host HTTP API.

Uses an isolated temporary profile, never the user's SINCAL installation.
"""
import argparse
import json
from pathlib import Path
import tempfile
import threading
from urllib.request import Request, urlopen
from unittest.mock import patch

from sincal.optional_modules import PasarelaModule
from sincal.web.server import Server


def check(package):
    with tempfile.TemporaryDirectory(prefix="sincal-module-integration-") as folder:
        root = Path(folder)
        application = root / "core"
        application.mkdir()
        core = application / "SINCAL.exe"
        core.write_bytes(b"Existing core remains unchanged")
        server = Server(0, root / "web")
        server.module_host = PasarelaModule(user_dir=root / "profile", application_dir=application, allow_source=False)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        auth = {"X-Sincal-Token": server.token}
        def call(route, data=None, mime="application/json"):
            request = Request(server.origin + "/api/modules/pasarela/" + route, data=data,
                              headers={**auth, "Content-Type": mime})
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        try:
            assert not call("status")["installed"]
            installed = call("install", Path(package).read_bytes(), "application/zip")
            assert installed["installed"] and installed["source"] == "user"
            with patch("sincal.optional_modules.webbrowser.open") as browser:
                started = call("open", b"{}")
                assert browser.call_count == 1
                assert call("open", b"{}")["url"] == started["url"]
            resources = {}
            for path in ("", "ejes.js", "api/estado"):
                with urlopen(started["url"] + path, timeout=15) as response:
                    resources[path or "/"] = response.status
                    assert response.status == 200
            assert call("status")["running"]
            original_process = server.module_host.process
            # Simulate reopening the main program while the separate editor is
            # still running; the host must reuse it and await its real shutdown.
            server.module_host = PasarelaModule(user_dir=root / "profile", application_dir=application, allow_source=False)
            assert call("status")["running"]
            assert not call("close", b"{}")["running"]
            assert original_process.poll() is not None
            assert not call("status")["running"]
            assert core.read_bytes() == b"Existing core remains unchanged"
            return {"ok": True, "package": str(Path(package).resolve()), "version": installed["version"],
                    "package_bytes": Path(package).stat().st_size, "http": resources,
                    "install_after_core": True, "core_unchanged": True,
                    "recovered_instance_closed_cleanly": True, "closed_cleanly": True}
        finally:
            if server.module_host.status()["running"]:
                server.module_host.close()
            server.shutdown()
            server.server_close()
            worker.join(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = check(args.package)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered)
