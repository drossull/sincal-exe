"""Construye sólo Pasarela BIM: ejecutable, ZIP verificable y complemento.

No instala el módulo, no publica archivos y no compila SINCAL, OCR ni CAD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, Request, build_opener
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MAX_ZIP_BYTES = 150 * 1024**2
MAX_INSTALLED_BYTES = 512 * 1024**2


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def descriptor(root=ROOT):
    data = json.loads((root/"packaging/windows/pasarela-bim/module.json").read_text(encoding="utf-8"))
    source = (root/"pasarela_bim/__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)',source)
    if not version or version[1] != data["version"]:
        raise ValueError("La versión del módulo no coincide con su manifiesto")
    if data.get("schema") != 1 or data.get("id") != "pasarela-bim" or data.get("host_api") != 1:
        raise ValueError("Contrato de módulo no compatible")
    if data.get("entrypoint") != "SINCAL-Pasarela.exe":
        raise ValueError("Punto de entrada del módulo no compatible")
    return data


def crear_paquete(executable, output, manifest):
    """Todos los archivos del ZIP salvo module.json quedan cubiertos por hash."""
    executable,output = Path(executable).resolve(),Path(output).resolve()
    if not executable.is_file() or executable.stat().st_size == 0:
        raise ValueError("Falta el ejecutable del módulo")
    if executable.stat().st_size > MAX_INSTALLED_BYTES:
        raise ValueError("El ejecutable excede el tamaño permitido")
    output.mkdir(parents=True,exist_ok=True)
    stage = output/"module-stage"
    stage.mkdir(exist_ok=True)
    target = stage/manifest["entrypoint"]
    if executable != target:
        shutil.copy2(executable,target)
    module = dict(manifest, files={manifest["entrypoint"]:sha256(target)})
    manifest_path = stage/"module.json"
    manifest_path.write_text(json.dumps(module,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    installed_bytes = target.stat().st_size+manifest_path.stat().st_size
    if installed_bytes > MAX_INSTALLED_BYTES:
        raise ValueError("El módulo excede el tamaño instalado permitido")
    archive = output/f"SINCAL_Pasarela_v{module['version']}.zip"
    # ZIP determinista para un mismo ejecutable y manifiesto. La lista cerrada
    # impide incorporar archivos antiguos del stage, datos o generados locales.
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as stream:
        for filename in (module["entrypoint"],"module.json"):
            info = zipfile.ZipInfo(filename,date_time=(2020,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            stream.writestr(info,(stage/filename).read_bytes())
    if archive.stat().st_size > MAX_ZIP_BYTES:
        archive.unlink()
        raise ValueError("El ZIP del módulo excede 150 MiB")
    return {"schema":1,"id":module["id"],"version":module["version"],"host_api":module["host_api"],
            "zip":str(archive),"sha256":sha256(archive),"bytes":archive.stat().st_size,
            "installed_bytes":installed_bytes,"executable":str(executable),"stage":str(stage)}


def localizar_iscc(provided=None):
    if provided:
        path = Path(provided)
        if not path.is_file():
            raise ValueError("No se encontró el compilador Inno Setup indicado")
        return path
    for folder in (os.environ.get("ProgramFiles(x86)","C:/Program Files (x86)"),
                   os.environ.get("ProgramFiles","C:/Program Files")):
        path = Path(folder)/"Inno Setup 6/ISCC.exe"
        if path.is_file():
            return path
    raise RuntimeError("No se encontró Inno Setup; use --skip-installer para obtener sólo el ZIP")


def smoke_test(executable, output):
    """Ejecuta el binario sin navegador ni instalaciones, con datos temporales."""
    with tempfile.TemporaryDirectory(prefix="pasarela-module-") as folder:
        directory = Path(folder)
        info = directory/"launch.json"
        env = os.environ.copy()
        env["PASARELA_DATA_DIR"] = str(directory/"datos")
        kwargs = {"creationflags":subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        process = subprocess.Popen([str(executable),"--port","0","--sin-navegador","--launch-info",str(info)],
                                   cwd=directory,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**kwargs)
        launch = None
        opener = build_opener(ProxyHandler({}))
        try:
            deadline = time.monotonic()+45
            while not info.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("El módulo terminó antes de iniciar su interfaz")
                time.sleep(0.1)
            if not info.exists():
                raise RuntimeError("El módulo no confirmó su inicio")
            launch = json.loads(info.read_text(encoding="utf-8"))
            url = launch["url"]
            if not re.fullmatch(r"http://127\.0\.0\.1:\d+/?",url):
                raise RuntimeError("La interfaz no se limitó al equipo local")
            results = {}
            for path in ("/","/api/estado","/api/ejemplo","/app.js","/style.css"):
                with opener.open(url.rstrip("/")+path,timeout=10) as response:
                    content = response.read()
                    if not content:
                        raise RuntimeError("Recurso vacío: "+path)
                    results[path] = {"status":response.status,"bytes":len(content)}
                    if path == "/api/estado":
                        results[path]["version"] = json.loads(content)["version"]
            report = {"valido":True,"pid":launch["pid"],"recursos":results}
            (Path(output)/"smoke-test.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
            return report
        finally:
            # Sólo se termina la instancia privada de este ensayo.
            if launch and process.poll() is None:
                try:
                    request = Request(launch["url"].rstrip("/")+"/api/cerrar",data=b"{}",
                                      headers={"Content-Type":"application/json",
                                               "X-Pasarela-Token":launch["control_token"]},method="POST")
                    with opener.open(request,timeout=10) as response:
                        response.read()
                    process.wait(timeout=15)
                except (OSError,KeyError,subprocess.TimeoutExpired):
                    pass
            if process.poll() is None:
                if os.name == "nt":
                    # El bootloader onefile tiene un hijo propio: cerrar sólo
                    # el padre dejaría el servidor de la prueba en ejecución.
                    subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--skip-build",action="store_true",help="Reempaquetar el ejecutable ya construido")
    parser.add_argument("--skip-installer",action="store_true")
    parser.add_argument("--iscc",type=Path)
    parser.add_argument("--smoke-test",action="store_true")
    args = parser.parse_args(argv)
    manifest = descriptor()
    output = (args.output_dir or ROOT/f"installer_output/pasarela-bim/v{manifest['version']}").resolve()
    output.mkdir(parents=True,exist_ok=True)
    executable = ROOT/"dist/pasarela-bim"/manifest["entrypoint"]
    if not args.skip_build:
        with (output/"pyinstaller.log").open("wb") as log:
            subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--clean",
                            "--distpath",str(executable.parent),"--workpath",str(ROOT/"build/pasarela-bim"),
                            str(ROOT/"packaging/windows/SINCAL_Pasarela.spec")],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    result = crear_paquete(executable,output,manifest)
    if not args.skip_installer:
        with (output/"inno.log").open("wb") as log:
            subprocess.run([str(localizar_iscc(args.iscc)),"/Qp",f"/DModuleVersion={manifest['version']}",
                            f"/DModuleStageDir={result['stage']}",f"/DModuleOutputDir={output}",
                            str(ROOT/"packaging/windows/SINCAL_Pasarela_Installer.iss")],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        result["installer"] = str(output/f"Setup_SINCAL_Pasarela_v{manifest['version']}.exe")
    if args.smoke_test:
        result["smoke_test"] = smoke_test(executable,output)
    report = output/"pasarela-module-build.json"
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
