"""Escena vectorial común a la previsualización y al dibujo CAD de perfiles Vs."""

from __future__ import annotations

import math
import uuid

from sincal.prospecciones import VsProfile, number


COLORS = {8: '#808080', 3: '#00ff00', 5: '#0000ff', 1: '#ff0000'}


def profile_scene(profile: VsProfile, include_table=True) -> list[dict]:
    """Coordenadas en mm de papel, Y hacia abajo; sin alterar la escala de Vs."""
    errors = profile.errors()
    if errors:
        raise ValueError('\n'.join(errors))
    scene = []

    def line(x1, y1, x2, y2, color=8):
        scene.append(dict(kind='line', points=[(x1, y1), (x2, y2)], color=color))

    def text(x, y, value, anchor='center'):
        scene.append(dict(kind='text', point=(x, y), text=str(value), color=3, anchor=anchor))

    width, height, top = 100, 150, 16
    maximum = max(number(row.vs) for row in profile.layers)
    power = 10 ** math.floor(math.log10(maximum / 5))
    step = next(mult * power for mult in (1, 2, 2.5, 5, 10) if mult * power >= maximum / 5)
    xmax = math.ceil(maximum / step) * step
    depth = max(30, number(profile.layers[-1].end))
    ystep = 5 if depth <= 40 else 10 ** math.ceil(math.log10(depth / 6))
    ymax = math.ceil(depth / ystep) * ystep
    text(width / 2, -2, profile.name + ' - Perfil Vs')
    text(width / 2, 5, 'Vs (m/s)')
    text(-10, top - 7, 'Prof. (m)')
    for index in range(round(xmax / step) + 1):
        value = index * step
        x = width * value / xmax
        line(x, top, x, top + height)
        line(x, top - 2, x, top, 1)
        text(x, top - 4, f'{value:g}')
    for index in range(round(ymax / ystep) + 1):
        value = index * ystep
        y = top + height * value / ymax
        line(0, y, width, y)
        line(-2, y, 0, y, 1)
        text(-4, y, f'{value:g}', 'right')
    points = []
    for row in profile.layers:
        x = width * number(row.vs) / xmax
        points.extend([(x, top + height * number(row.start) / ymax),
                       (x, top + height * number(row.end) / ymax)])
    scene.append(dict(kind='polyline', points=points, color=5))
    for point in dict.fromkeys(points):
        scene.append(dict(kind='circle', point=point, radius=1, color=1))
    y = top + height + 7
    official = f'{profile.official_vs30} m/s' if profile.official_vs30 else 'No identificado'
    text(0, y, 'Vs,30 oficial = ' + official, 'left')
    text(0, y + 5, f'Fuente: informe, pagina PDF {profile.page}', 'left')
    if include_table:
        y += 12
        columns = [0, 12, 40, 68, 100]
        values = [['N.', 'Inicio (m)', 'Final (m)', 'Vs (m/s)']]
        values.extend([[str(row.index), row.start, row.end, row.vs] for row in profile.layers])
        for i, row in enumerate(values):
            line(0, y + i * 6, width, y + i * 6)
            for j, value in enumerate(row):
                text((columns[j] + columns[j + 1]) / 2, y + i * 6 + 3, value)
        line(0, y + len(values) * 6, width, y + len(values) * 6)
        for x in columns:
            line(x, y, x, y + len(values) * 6)
    return scene


def lisp_string(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\r', ' ').replace('\n', ' ') + '"'


def build_profile_lisp(profile: VsProfile, include_table=True) -> str:
    scene = profile_scene(profile, include_table)

    def point(p):
        return f'(sp:p {p[0]:.9g} {p[1]:.9g})'

    commands = []
    for item in scene:
        kind, color = item['kind'], item['color']
        if kind in ('line', 'polyline'):
            pts = item['points']
            for a, b in zip(pts, pts[1:]):
                commands.append(f'(sp:add (vla-AddLine ms {point(a)} {point(b)}) {color})')
        elif kind == 'circle':
            commands.append(f'(sp:add (vla-AddCircle ms {point(item["point"])} (* k 1.0)) {color})')
        elif kind == 'text':
            # MText treats braces and backslashes as formatting, not source text.
            label = item['text'].replace('\\', '/').replace('{', '(').replace('}', ')')
            attachment = {'left': 4, 'center': 5, 'right': 6}[item['anchor']]
            commands.append(f'(sp:text {point(item["point"])} {lisp_string(label)} {attachment})')
    body = '\n        '.join(commands)
    group_name = 'SINCAL_VS_' + uuid.uuid4().hex
    # Helpers are local to the command. Only newly created objects are rolled
    # back on failure or Esc. No save, erase-existing, or document switching.
    return f'''(vl-load-com)
(defun c:SINCAL-PROSPECCIONES (/ *error* sp:p sp:add sp:text doc ms base k created grp arr result obj en oldecho undo)
  (defun *error* (msg)
    (foreach obj created (vl-catch-all-apply 'vla-Delete (list obj)))
    (if grp (vl-catch-all-apply 'vla-Delete (list grp)))
    (if undo (vla-EndUndoMark doc))
    (if oldecho (setvar "CMDECHO" oldecho))
    (princ (strcat "\\n[SINCAL] Insercion cancelada: " msg)) (princ))
  (defun sp:p (x y)
    (vlax-3d-point (list (+ (car base) (* k x)) (- (cadr base) (* k y)) (caddr base))))
  (defun sp:add (obj color)
    (setq created (cons obj created))
    (vla-put-Layer obj "0")
    (vla-put-Color obj color)
    (vla-put-Linetype obj "Continuous")
    obj)
  (defun sp:text (pt label attachment / txt ent result)
    (setq txt (sp:add (vla-AddMText ms pt (* k 140.0) label) 3))
    (vla-put-StyleName txt "RomanD")
    (vla-put-Height txt (* k 2.5))
    (vla-put-AttachmentPoint txt attachment)
    (vla-put-InsertionPoint txt pt)
    (setq ent (vlax-vla-object->ename txt))
    (setq result (vl-catch-all-apply 'setpropertyvalue (list ent "Annotative" 1)))
    (if (vl-catch-all-error-p result)
      (progn
        (regapp "AcadAnnotative")
        (if (not (entmod (append (entget ent)
          '((-3 ("AcadAnnotative" (1000 . "AnnotativeData") (1002 . "{{") (1070 . 1) (1070 . 1) (1002 . "}}")))))))
          (progn (princ "No se pudo activar el texto anotativo.") (exit)))))
    (vl-cmdf "_.-OBJECTSCALE" ent "" "_Add" (getvar "CANNOSCALE") "")
    (vla-put-Height txt (* k 2.5))
    (vla-put-InsertionPoint txt pt))
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)) ms (vla-get-ModelSpace doc))
  (cond
    ((/= (getvar "INSUNITS") 6) (alert "Prospecciones requiere un dibujo en metros (INSUNITS=6)."))
    ((= (getvar "CVPORT") 1) (alert "Activa Model antes de insertar el perfil Vs."))
    ((not (tblsearch "STYLE" "RomanD")) (alert "Falta el estilo RomanD. Carga el master SINCAL antes de insertar."))
    ((/= 0 (logand 5 (cdr (assoc 70 (tblsearch "LAYER" "0")))) )
      (alert "La capa 0 debe estar descongelada y desbloqueada."))
    (T
      (setq base (getpoint "\\nPunto superior izquierdo del perfil Vs: "))
      (if base
        (progn
          (setq base (trans base 1 0) k (/ 1.0 (getvar "CANNOSCALEVALUE")))
          (setq oldecho (getvar "CMDECHO")) (setvar "CMDECHO" 0)
          (vla-StartUndoMark doc) (setq undo T)
          {body}
          (setq grp (vla-Add (vla-get-Groups doc) "{group_name}"))
          (setq arr (vlax-make-safearray vlax-vbObject (cons 0 (1- (length created)))))
          (vlax-safearray-fill arr (reverse created))
          (vla-AppendItems grp arr)
          (vla-EndUndoMark doc) (setq undo nil)
          (setvar "CMDECHO" oldecho)
          (vla-Regen doc 1)
          (princ "\\n[SINCAL] Perfil Vs vectorial insertado. Valores oficiales conservados.")))))
  (princ))
'''
