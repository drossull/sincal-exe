"""Perfiles de alas compartidos por moldajes y armadura, sin acceso a CAD.

La escena usa metros; los parámetros editables se entregan en centímetros.
Las cotas del camino inferidas del JSON son nominales hasta su confirmación.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math


GEOMETRY_FIELDS = (
    "thickness_cm", "main_length_cm", "extension_length_cm", "top_join_cm",
    "top_edge_cm", "top_tip_cm", "tip_height_cm", "front_height_cm",
    "front_depth_cm", "back_thickness_cm",
)


def _number(value, name, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or value > 100000
            or (positive and value <= 0)):
        raise ValueError(f"Completa una medida válida del ala: {name}.")
    return float(value)


def _point(values, label):
    if (not isinstance(values, (tuple, list)) or len(values) != 3
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in values)):
        raise ValueError(f"Referencia del ala inválida: {label}.")
    return tuple(float(value) for value in values)


def _unique(points):
    result = []
    for point in points:
        point = tuple(point)
        if not result or math.dist(point, result[-1]) > 1e-10:
            result.append(point)
    if len(result) > 1 and math.dist(result[0], result[-1]) < 1e-10:
        result.pop()
    return tuple(result)


def extract_geometry(project, instance, side, footing_state=None):
    """Extrae el perfil nominal, conservando los valores originales del JSON."""
    side = {"izq": "left", "der": "right"}.get(side, side)
    if side not in ("left", "right"):
        raise ValueError("Selecciona el ala izquierda o derecha.")
    from .abutment_scene import build_scene
    scene = build_scene(project, instance, footing_state,
                        use_state_geometry=footing_state is not None, include_wing_rebar=False)
    metadata = scene.get("wing_geometry", {}).get(side)
    if metadata is None:
        reasons = "; ".join(scene.get("issues", ()))
        raise ValueError("No se pudo definir el moldaje de esta ala. " + reasons)
    return deepcopy(metadata)


def build_wing_profile(metadata, overrides=None):
    """Construye una unión única de frontal, ala principal y aleta.

    u=0 está en la cara trasera del espaldar y crece hacia el relleno.
    La diagonal parte en (largo principal, 0), sobre la zapata; no se copia
    el solape de 1 mm usado por el modelador de sólidos de Proyecto Puentes.
    Los overrides modifican sólo este perfil, nunca frontal/espaldar globales.
    """
    if not isinstance(metadata, Mapping) or not isinstance(metadata.get("geometry"), Mapping):
        raise ValueError("Falta la geometría del ala.")
    if overrides is not None and not isinstance(overrides, Mapping):
        raise ValueError("Los parámetros del ala deben ser un objeto.")
    original = metadata["geometry"]
    values = dict(original)
    values.update({key: value for key, value in (overrides or {}).items() if key in GEOMETRY_FIELDS})
    geometry = {key: _number(values.get(key), key,
                             positive=key in ("thickness_cm", "main_length_cm", "top_join_cm",
                                              "top_edge_cm", "top_tip_cm", "front_height_cm"))
                for key in GEOMETRY_FIELDS}
    g = {key: value / 100 for key, value in geometry.items()}
    joint, reach = g["main_length_cm"], g["extension_length_cm"]
    tip = joint + reach
    active = metadata.get("extension_enabled") is True
    if not active and reach > 0:
        raise ValueError("El JSON no activa una aleta para este muro.")
    if active and (reach <= 0 or not 0 < g["tip_height_cm"] <= g["top_tip_cm"]):
        raise ValueError("La altura mínima de la aleta debe ser positiva y no superar su coronación sobre la zapata.")
    depth, back = g["front_depth_cm"], g["back_thickness_cm"]
    if back > depth + 1e-9:
        raise ValueError("El espaldar no cabe entre el ala y la cara frontal libre.")
    frame = metadata.get("frame", {})
    origin = _point(frame.get("origin_m"), "origen")
    axis = _point(frame.get("axis_u"), "eje longitudinal")
    inward = _point(frame.get("inward"), "normal interior")
    front_axis = _point(frame.get("front_axis_u", axis), "eje hacia el frontal")
    front_inward = _point(frame.get("front_inward", inward), "normal interior del frontal")
    if (abs(axis[2]) > 1e-9 or abs(inward[2]) > 1e-9
            or abs(math.sqrt(sum(v*v for v in axis))-1) > 1e-8
            or abs(math.sqrt(sum(v*v for v in inward))-1) > 1e-8
            or abs(sum(a*b for a,b in zip(axis, inward))) > 1e-8):
        raise ValueError("Los ejes del ala no definen un plano vertical válido.")
    join_z, edge_z, tip_z = g["top_join_cm"], g["top_edge_cm"], g["top_tip_cm"]
    bottom_tip = tip_z-g["tip_height_cm"] if active else 0.0
    main = ((0., 0.), (joint, 0.), (joint, edge_z), (0., join_z))
    extension = ((joint, 0.), (tip, bottom_tip), (tip, tip_z), (joint, edge_z)) if active else ()
    # The road slope across the back-wall thickness remains the nominal one.
    # Editing top_join translates that short local profile, without editing
    # the separately displayed back wall or the source JSON.
    back_top_delta = float(metadata.get("back_front_top_delta_cm", 0.0)) / 100
    upper = []
    if depth > 0:
        upper.extend(((-depth, g["front_height_cm"]), (-back, g["front_height_cm"])))
    if back > 0:
        upper.append((-back, join_z + back_top_delta))
    upper.extend(((0., join_z), (joint, edge_z)))
    if active:
        upper.append((tip, tip_z))
    upper = _unique(upper)
    lower = _unique(((-depth, 0.), (0., 0.), (joint, 0.), *((((tip, bottom_tip),) if active else ()))))
    exterior = _unique((*lower, *reversed(upper)))

    def world(point):
        u, z = point
        direction = front_axis if u < 0 else axis
        return tuple(origin[i] + u*direction[i] + (z if i == 2 else 0.0) for i in range(3))

    # Keep the real shear of the footprint (start/end lie on skewed faces).
    # The scalar UI thickness is its perpendicular component, not its ΔX.
    side_offset = _point(metadata.get("side_offset_m"), "espesor en planta")
    shear = sum(a*b for a,b in zip(side_offset, axis))
    inner_offset = tuple(shear*axis[i] + g["thickness_cm"]*inward[i] for i in range(3))
    # Without an extension, the historic unrotated end is Y=constant. Its
    # inner edge can be shorter than its outer edge when the support is skewed.
    inner_end_delta = float(metadata.get("inner_main_length_delta_m", 0.0))

    def offset_at(u):
        fraction = min(1., max(0., u/joint))
        return tuple(inner_offset[i]+axis[i]*inner_end_delta*fraction for i in range(3))

    def footprint(first, last):
        a, b = world((first, 0)), world((last, 0))
        da, db = offset_at(first), offset_at(last)
        return (a[:2], tuple(a[i]+da[i] for i in range(2)),
                tuple(b[i]+db[i] for i in range(2)), b[:2])

    def mesh(profile):
        outer = [world(point) for point in profile]
        def top_delta(u):
            joins = ((0., "inner_top_join_delta_cm"), (joint, "inner_top_edge_delta_cm"),
                     (tip, "inner_top_tip_delta_cm")) if active else (
                         (0., "inner_top_join_delta_cm"), (joint, "inner_top_edge_delta_cm"))
            for (a, ka), (b, kb) in zip(joins, joins[1:]):
                if u <= b + 1e-9:
                    va, vb = float(metadata.get(ka, 0))/100, float(metadata.get(kb, 0))/100
                    return va + (vb-va) * (u-a)/(b-a)
            return float(metadata.get(joins[-1][1], 0))/100
        inner = [tuple(point[i]+offset_at(profile[j][0])[i] + (top_delta(profile[j][0]) if i == 2 and j >= 2 else 0)
                       for i in range(3)) for j, point in enumerate(outer)]
        n = len(outer)
        return {"vertices": [list(p) for p in (*outer, *inner)],
                "faces": [list(reversed(range(n))), list(range(n,2*n))]
                         + [[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]}

    source_issues = list(metadata.get("source_issues", metadata.get("issues", ())))
    issues = list(source_issues)
    changed = [key for key in GEOMETRY_FIELDS
               if not math.isclose(geometry[key], float(original[key]), abs_tol=1e-7)]
    if changed:
        issues.append("Perfil del ala con medidas editadas; el JSON original se conserva.")
    if any(key in changed for key in ("top_join_cm", "front_height_cm", "front_depth_cm", "back_thickness_cm")):
        issues.append("El perfil editado del ala difiere del frontal o espaldar nominal; esos moldajes globales no se modificaron.")
    source = metadata.get("source", {})
    maximum = source.get("alto_maximo_aleta_cm")
    if active and maximum is not None and abs(float(maximum)-geometry["top_tip_cm"]) > 1e-4:
        issues.append("El alto máximo de aleta del JSON no coincide con la coronación del extremo libre respecto de la zapata; revisa las cotas para confirmar la diagonal hasta su borde.")
    result = deepcopy(dict(metadata))
    result.update(geometry=geometry, frame={"origin_m": origin, "axis_u": axis,
                                          "inward": inward, "axis_z": (0.,0.,1.),
                                          "front_axis_u": front_axis, "front_inward": front_inward},
                  main_footprint_m=footprint(0, joint),
                  extension_footprint_m=footprint(joint, tip) if active else (),
                  main_profile_m=main, extension_profile_m=extension,
                  exterior_profile_m=exterior, upper_profile_m=upper, lower_profile_m=lower,
                  main_vertices_m=tuple(map(world, main)),
                  extension_vertices_m=tuple(map(world, extension)),
                  exterior_vertices_m=tuple(map(world, exterior)),
                  meshes=[mesh(main)] + ([mesh(extension)] if active else []),
                  quality="nominal", geometry_confirmed=False,
                  geometry_edited=bool(changed) or metadata.get("geometry_edited", False),
                  source_issues=source_issues,
                  issues=list(dict.fromkeys(issues)))
    return result
