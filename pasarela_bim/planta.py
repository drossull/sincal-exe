"""Reference plan import. The uploaded copy is isolated from CAD sessions."""
from __future__ import annotations

from collections import Counter
import math
import os
from pathlib import Path
import subprocess
import time
import uuid
from .runtime import entorno_externo, bibliotecas_sistema

MAX_UPLOAD = 20 * 1024 * 1024
MAX_ENTITIES = 25000
MAX_POINTS = 250000
MAX_CONVERTED = 100 * 1024 * 1024


def _version_registro_motor(motor):
    """Read the executable version; AutoCAD year and registry release differ."""
    import ctypes
    version = ctypes.windll.version
    size = version.GetFileVersionInfoSizeW(str(motor), None)
    if not size:
        raise ValueError("No se pudo identificar la versión del conversor instalado.")
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(motor), 0, size, data):
        raise ValueError("No se pudo identificar la versión del conversor instalado.")
    pointer, length = ctypes.c_void_p(), ctypes.c_uint()
    if not version.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise ValueError("No se pudo identificar la versión del conversor instalado.")
    fixed = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
    number = fixed[2]  # VS_FIXEDFILEINFO.dwFileVersionMS
    return f"R{number >> 16}.{number & 65535}"


def _preparar_perfil_aislado(motor, usuario):
    """Seed only this worker's CoreUser hive, never the interactive CAD profile.

    /isolate alone copies the user's profile, including startup support paths.
    A separate named profile prevents those routines from touching the copy.
    CoreConsole 2025 ignores /safemode, so that switch is deliberately not used.
    """
    import winreg
    version = _version_registro_motor(motor)
    base = (rf"Software\AppDataLow\Software\Autodesk\AutoCAD\{version}"
            rf"\CoreUser\{usuario}\Profiles\PASARELA_IMPORT")
    support = ";".join(str(motor.parent / name) for name in
                       ("Support", "Support/en-US", "Fonts"))
    for suffix in ("General", "Variables"):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + "\\" + suffix) as key:
            for name in ("APPAUTOLOAD", "DEMANDLOAD"):
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "ACAD", 0, winreg.REG_SZ, support)


def _script_conversion(destino, marcador, token):
    def quoted(path):
        return '"' + path.as_posix().replace('"', '\\"') + '"'
    # The marker is closed only after DXFOUT returns. The source DWG is never saved.
    return ('(setvar "FILEDIA" 0)\n(setvar "CMDECHO" 0)\n'
            '(setq pb-units (getvar "INSUNITS"))\n'
            '(setq pb-clean (and (= (getvar "CPROFILE") "PASARELA_IMPORT") '
            '(= (getvar "APPAUTOLOAD") 0) (null (findfile "acad.lsp")) '
            '(null (findfile "acaddoc.lsp"))))\n'
            '(if pb-clean (progn (command "_.DXFOUT" ' + quoted(destino)
            + ' "_Version" "2013" "16") '
            '(if (findfile ' + quoted(destino) + ') (progn '
            '(setq pb-marker (open ' + quoted(marcador) + ' "w")) '
            '(write-line "' + token + '" pb-marker) '
            '(write-line (itoa pb-units) pb-marker) '
            '(write-line (itoa (getvar "INSUNITS")) pb-marker) '
            '(close pb-marker)))))\n(princ)\n_.QUIT\n_Y\n')


def _exportacion_completa(destino, marcador, token):
    """Return declared units only for a matching, closed export and complete DXF."""
    try:
        lines = marcador.read_text(encoding="ascii").splitlines()
        if len(lines) != 3 or lines[0] != token:
            return None
        try:
            before, after = int(lines[1]), int(lines[2])
        except ValueError:
            return None  # The writer may still be completing the marker.
        if before != after:
            raise ValueError("Las unidades del dibujo cambiaron durante la conversión. Carga un DXF verificado.")
        size = destino.stat().st_size
        if size > MAX_CONVERTED:
            raise ValueError("La planta convertida es demasiado grande; exporta sólo el sector de la pasarela.")
        if not size:
            return None
        with destino.open("rb") as source:
            source.seek(max(0, size-128))
            tail = source.read().splitlines()
        if len(tail) < 2 or tail[-2].strip() != b"0" or tail[-1].strip() != b"EOF":
            return None
        return before
    except (OSError, UnicodeError):
        return None


def _esperar_conversion(process, destino, marcador, token, timeout=90):
    deadline = time.monotonic() + timeout
    confirmed, signature, units = None, None, None
    while time.monotonic() < deadline:
        units = _exportacion_completa(destino, marcador, token)
        if units is not None:
            stat = destino.stat()
            current = (stat.st_size, stat.st_mtime_ns)
            if current != signature:
                signature, confirmed = current, time.monotonic()
            if process.poll() is not None or time.monotonic()-confirmed >= 1:
                return units
        if process.poll() is not None:
            break
        time.sleep(.1)
    if units is None:
        raise ValueError("La conversión DWG no pudo confirmar una exportación completa. Prueba con un DXF del mismo sector.")
    raise ValueError("La conversión DWG no terminó de escribir el archivo. Prueba con DXF.")


def _unidades_cabecera(datos):
    # INSUNITS is a header variable; avoid decoding the entire geometry twice.
    lines = datos[:2*1024*1024].decode("ascii", errors="replace").splitlines()
    for index in range(0, len(lines)-3, 2):
        if lines[index].strip() == "9" and lines[index+1].strip() == "$INSUNITS":
            return int(lines[index+3].strip())
        if lines[index].strip() == "0" and lines[index+1].strip() == "ENDSEC":
            break
    return 0


def localizar_conversor():
    base = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Autodesk"
    candidates = sorted(base.glob("AutoCAD */accoreconsole.exe"), reverse=True)
    return next((p for p in candidates if "2025" in str(p)), candidates[0] if candidates else None)


def convertir_dwg(datos: bytes, carpeta: Path):
    carpeta = carpeta.resolve()
    motor = localizar_conversor()
    if motor is None:
        raise ValueError("Para leer DWG se necesita AutoCAD Core Console instalado. Puedes cargar un DXF en metros.")
    if not datos.startswith(b"AC10"):
        raise ValueError("El archivo no contiene una cabecera DWG reconocible.")
    carpeta.mkdir(parents=True, exist_ok=False)
    origen, destino = carpeta / "entrada.dwg", carpeta / "planta.dxf"
    origen.write_bytes(datos)
    token = uuid.uuid4().hex
    usuario = "PasarelaBIM_" + token
    _preparar_perfil_aislado(motor, usuario)
    marcador = carpeta / "exportacion.completa"
    script = carpeta / "exportar.scr"
    script.write_text(_script_conversion(destino, marcador, token), encoding="utf-8")
    with (carpeta / "conversion.log").open("wb") as log:
        with bibliotecas_sistema():
            process = subprocess.Popen([str(motor), "/i", str(origen), "/s", str(script), "/l", "en-US",
                "/readonly", "/isolate", usuario, str(carpeta / "perfil"), "/p", "PASARELA_IMPORT"],
                cwd=carpeta, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=entorno_externo(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            units = _esperar_conversion(process, destino, marcador, token)
        finally:
            # QUIT can leave CoreConsole waiting even after successful export.
            # Terminate only this Popen handle; never enumerate or close CAD GUIs.
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
    exported = destino.read_bytes()
    if _unidades_cabecera(exported) != units:
        raise ValueError("Las unidades del archivo exportado no coinciden con el dibujo. Carga un DXF verificado.")
    return exported


def leer_dxf(datos: bytes, nombre="planta.dxf"):
    if datos.startswith(b"AutoCAD Binary DXF"):
        raise ValueError("Exporta el DXF en formato ASCII para cargarlo como planta.")
    try:
        text = datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = datos.decode("cp1252", errors="replace")
    lines = text.splitlines()
    if len(lines) % 2:
        raise ValueError("El archivo DXF está incompleto.")
    try:
        pairs = [(int(lines[i].strip()), lines[i+1].strip()) for i in range(0, len(lines), 2)]
    except ValueError:
        raise ValueError("No se reconoce el formato de grupos del DXF.")
    if not any(code == 0 and value == "SECTION" for code, value in pairs):
        raise ValueError("No se encontraron secciones DXF.")
    unit = 0
    for i, item in enumerate(pairs[:-1]):
        if item == (9, "$INSUNITS"):
            unit = int(pairs[i+1][1])
            break
    factors = {0:1, 1:.0254, 2:.3048, 4:.001, 5:.01, 6:1, 7:1000}
    if unit not in factors:
        raise ValueError("Unidades DWG/DXF no compatibles; exporta la planta en metros.")
    factor = factors[unit]
    warnings = []
    if unit == 0:
        warnings.append("El dibujo no declara unidades. Se interpreta en metros; comprueba una distancia conocida.")
    elif unit != 6:
        warnings.append("Las unidades declaradas del dibujo se convirtieron a metros.")
    records, current = [], None
    for code, value in pairs:
        if code == 0:
            current = {"type":value, "data":[]}
            records.append(current)
        elif current is not None:
            current["data"].append((code,value))
    def val(r, code, default=None):
        return next((v for k,v in r["data"] if k == code), default)
    def num(r, code, default=0):
        result = float(val(r, code, default))
        if not math.isfinite(result) or abs(result) > 1e12:
            raise ValueError("El dibujo contiene coordenadas fuera de rango.")
        return result
    blocks, entities, section, active = {}, [], None, None
    for r in records:
        kind = r["type"]
        if kind == "SECTION": section = val(r,2)
        elif kind == "ENDSEC": section = None
        elif section == "BLOCKS":
            if kind == "BLOCK":
                active = {"base":[num(r,10),num(r,20),num(r,30)], "records":[], "xref":bool(int(num(r,70)) & 4)}
                blocks[val(r,2)] = active
            elif kind == "ENDBLK": active = None
            elif active is not None: active["records"].append(r)
        elif section == "ENTITIES": entities.append(r)
    result, omitted, point_count = [], Counter(), 0
    def emit(points, layer, label=None):
        nonlocal point_count
        if len(result) >= MAX_ENTITIES or point_count + len(points) > MAX_POINTS:
            raise ValueError("Demasiada geometría. Exporta sólo la planta del sector de la pasarela.")
        point_count += len(points)
        entity = {"capa":layer, "puntos_m":[[v*factor for v in p] for p in points]}
        if label is not None: entity["texto"] = label[:240]
        result.append(entity)
    def bulge_segment(a,b,bulge):
        if abs(bulge) < 1e-12: return [a]
        dx,dy = b[0]-a[0],b[1]-a[1]
        if math.hypot(dx,dy) < 1e-10: return [a]
        cx = (a[0]+b[0])/2-dy*(1-bulge*bulge)/(4*bulge)
        cy = (a[1]+b[1])/2+dx*(1-bulge*bulge)/(4*bulge)
        start, sweep = math.atan2(a[1]-cy,a[0]-cx),4*math.atan(bulge)
        radius = math.hypot(a[0]-cx,a[1]-cy)
        steps = max(2,math.ceil(abs(sweep)/(math.pi/36)))
        return [[cx+radius*math.cos(start+sweep*i/steps),cy+radius*math.sin(start+sweep*i/steps),a[2]+(b[2]-a[2])*i/steps] for i in range(steps)]
    def walk(items, transform=lambda p:p, inherited="0", depth=0):
        if depth > 8:
            omitted["bloques anidados"] += 1
            return
        i = 0
        while i < len(items):
            r = items[i]; i += 1
            kind = r["type"]
            if int(num(r,67)) == 1 or num(r,60) == 1: continue
            layer = val(r,8,"0")
            if layer == "0": layer = inherited
            normal = [num(r,210),num(r,220),num(r,230,1)]
            if kind in ("ARC","CIRCLE","LWPOLYLINE","INSERT") and normal != [0,0,1]:
                omitted["entidades con plano inclinado"] += 1
                continue
            point = lambda base=10:[num(r,base),num(r,base+10),num(r,base+20)]
            pts, label = [], None
            if kind == "LINE": pts = [point(),point(11)]
            elif kind in ("LWPOLYLINE","POLYLINE"):
                vertices, bulges = [], []
                if kind == "LWPOLYLINE":
                    for code,value in r["data"]:
                        if code == 10: vertices.append([float(value),0,num(r,38)]); bulges.append(0)
                        elif code == 20 and vertices: vertices[-1][1] = float(value)
                        elif code == 42 and bulges: bulges[-1] = float(value)
                else:
                    while i < len(items) and items[i]["type"] == "VERTEX":
                        v = items[i]; i += 1
                        vertices.append([num(v,10),num(v,20),num(v,30)]); bulges.append(num(v,42))
                    if int(num(r,70)) & (16|64):
                        omitted["mallas"] += 1
                        continue
                if vertices:
                    closed = int(num(r,70)) & 1
                    if closed: vertices.append(vertices[0])
                    for j in range(len(vertices)-1): pts.extend(bulge_segment(vertices[j],vertices[j+1],bulges[j]))
                    pts.append(vertices[-1])
            elif kind in ("CIRCLE","ARC"):
                cx,cy,cz = point(); radius = num(r,40)
                start = math.radians(num(r,50)) if kind == "ARC" else 0
                sweep = (math.radians(num(r,51))-start)%(2*math.pi) if kind == "ARC" else 2*math.pi
                steps = max(2,math.ceil(sweep/(math.pi/36)))
                pts = [[cx+radius*math.cos(start+sweep*j/steps),cy+radius*math.sin(start+sweep*j/steps),cz] for j in range(steps+1)]
            elif kind in ("TEXT","MTEXT","ATTRIB"):
                pts = [point()]; label = "".join(v for k,v in r["data"] if k in (1,3)).replace("\\P"," ")
            elif kind == "POINT": pts = [point()]
            elif kind == "INSERT":
                block = blocks.get(val(r,2))
                if not block or block["xref"]:
                    omitted["referencias externas o bloques ausentes"] += 1
                    continue
                x,y,z = point(); sx,sy,sz = num(r,41,1),num(r,42,1),num(r,43,1)
                angle = math.radians(num(r,50)); c,s = math.cos(angle),math.sin(angle)
                bx,by,bz = block["base"]
                def moved(p):
                    px,py = (p[0]-bx)*sx,(p[1]-by)*sy
                    return transform([x+px*c-py*s,y+px*s+py*c,z+(p[2]-bz)*sz])
                if num(r,70,1)>1 or num(r,71,1)>1: omitted["repeticiones de bloque (se muestra primera instancia)"] += 1
                walk(block["records"],moved,layer,depth+1)
                continue
            elif kind not in ("SEQEND","VERTEX"):
                omitted[kind] += 1
            if pts:
                transformed = [transform(p) for p in pts]
                if any(not all(math.isfinite(v) and abs(v)<1e12 for v in p) for p in transformed):
                    raise ValueError("El dibujo contiene coordenadas no válidas.")
                emit(transformed,layer,label)
    walk(entities)
    if omitted:
        warnings.append("No se representan todas las entidades: " + ", ".join(f"{k} ({v})" for k,v in sorted(omitted.items())) + ".")
    if not result:
        raise ValueError("No se encontró geometría compatible en el espacio modelo. Vincula las referencias externas y exporta la planta.")
    return {"nombre":Path(nombre).name,"unidades":"m","marco":"este_norte","entidades":result,
            "capas":sorted({e["capa"] for e in result}),"capas_ocultas":[],"visible":True,"avisos":warnings}


def importar_planta(datos, nombre, raiz):
    if not datos or len(datos) > MAX_UPLOAD:
        raise ValueError("Carga un DWG o DXF de hasta 20 MB.")
    suffix = Path(nombre).suffix.lower()
    if suffix == ".dwg": datos = convertir_dwg(datos, Path(raiz) / uuid.uuid4().hex)
    elif suffix != ".dxf": raise ValueError("Carga un archivo DWG o DXF.")
    return leer_dxf(datos,nombre)
