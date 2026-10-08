"""Single paper-space scene for preview and native CAD stratigraphic columns."""
import math
import re
import uuid

from sincal.prospecciones import number
from sincal.cad.prospecciones import lisp_string
from sincal.stratigraphy_hatches import HATCHES


def drawing_label(value):
    """Drawing typography only: never change the official report/session text."""
    return ''.join(part if part in ('m', 'm/s') else part.upper()
                   for part in re.split(r'(\bm(?:/s)?\b)', str(value)))


def mtext_label(value):
    # Sanitize documentary text before adding our own trusted MTEXT formatting.
    safe = value.replace('\\', '/').replace('{', '(').replace('}', ')')
    return re.sub(r'\bNSPT\b', lambda _: r'N{\H0.7x;\S^SPT;}', safe).replace('\n', '\\P')


def stratigraphy_scene(hole, include_table=False):
    errors = hole.errors()
    if errors:
        raise ValueError('\n'.join(errors))
    scene = []
    def line(a, b, color=8):
        scene.append(dict(kind='line', points=[a, b], color=color))
    def text(x, y, label, anchor='center'):
        scene.append(dict(kind='text', point=[x, y], text=drawing_label(label), anchor=anchor, color=3, height=2.5))
    drilled_depth = max(number(r.end) for r in hole.intervals)
    depth = max(drilled_depth, max((number(b.end) for b in hole.vs_bands), default=0))
    height = max(150, depth*8)
    top, gx, width = 27, 38, 80
    def y(d):
        return top+number(d)*height/depth
    text(0, 0, f'Sondaje {hole.name}', 'left')
    text(0, 7, 'Estratigrafía según operador', 'left')
    text(0, 20, 'Prof. (m)', 'left')
    text(gx+width/2, 7, 'NSPT (golpes/pie)')
    text(gx+width/2, 18, 'Recuperación (%) · azul')
    nmax = max(50, math.ceil(max((number(t.nspt) for t in hole.tests if not t.refusal), default=0)/10)*10)
    for i in range(11):
        x = gx + width*i/10
        line([x, top], [x, y(drilled_depth)])
        if i % 2 == 0:
            line([x, top-2], [x, top], 1)
            line([x, 11], [x, 13], 1)
            text(x, 23, i*10)
            text(x, 10, f'{nmax*i/10:g}')
    line([gx, 13], [gx+width, 13])
    step = max(1, math.ceil(depth/40))
    for d in sorted(set([*range(0, math.ceil(depth), step), depth])):
        yy = y(d)
        if d <= drilled_depth:
            line([gx, yy], [gx+width, yy])
        line([9, yy], [12, yy], 1)
        text(7, yy, f'{d:g}', 'right')
    previous = None
    for row in hole.intervals:
        a, b = number(row.start), number(row.end)
        if b <= a:
            continue  # Zero-length refused tests are NOT soil layers or zero-% segments.
        for name in [row.material, *row.inclusions]:
            scene.append(dict(kind='hatch', bounds=[12, y(a), 26, y(b)], material=name, color=8))
        for u, v in [([12,y(a)],[26,y(a)]),([12,y(b)],[26,y(b)]),([12,y(a)],[12,y(b)]),([26,y(a)],[26,y(b)])]:
            line(u, v, 1)
        x = gx + width*number(row.recovery)/100
        if previous and abs(a-previous[1]) < .011:
            line([previous[0], y(a)], [x, y(a)], 5)
        line([x, y(a)], [x, y(b)], 5)
        previous = (x, b)
    previous = None
    for test in hole.tests:
        yy = y(test.start)
        if test.refusal:
            text(gx+width+5, yy, 'R', 'left')
            line([gx+width+1, yy], [gx+width+3, yy], 1)
            previous = None  # Refusal has no numeric N; never interpolate through it.
        else:
            point = [gx+width*number(test.nspt)/nmax, yy]
            if previous:
                line(previous, point, 1)
            scene.append(dict(kind='circle', point=point, radius=.8, color=1))
            previous = point
    if hole.vs_bands:
        text(158, 18, 'Vs por tramo (m/s)')
        for band in hole.vs_bands:
            a, b = y(band.start), y(band.end)
            mid = (a+b)/2
            line([134,a], [182,a], 1)
            line([134,b], [182,b], 1)
            line([158,a], [158,mid-2], 1)
            line([158,mid+2], [158,b], 1)
            for tip, inside in [(a,a+1.6),(b,b-1.6)]:
                scene.append(dict(kind='triangle', points=[[158,tip],[157.4,inside],[158.6,inside]], color=1))
            text(158, mid, band.label)
        for bound in dict.fromkeys(v for b in hole.vs_bands for v in (b.start,b.end)):
            text(185, y(bound), bound+' m', 'left')
    legend_x = 215 if hole.vs_bands else 137
    legend_y = 32
    for name in dict.fromkeys(name for r in hole.intervals if number(r.end)>number(r.start) for name in [r.material,*r.inclusions]):
        scene.append(dict(kind='hatch', bounds=[legend_x, legend_y, legend_x+14, legend_y+5], material=name, color=8))
        text(legend_x+18, legend_y+2.5, HATCHES[name]['label'], 'left')
        legend_y += 9
    text(legend_x, legend_y+4, 'R = rechazo (no equivale a 50)', 'left')
    text(legend_x, legend_y+10, 'NSPT a profundidad DESDE', 'left')
    bottom = top+height
    text(0, bottom+7, 'Fuente: tablas del informe, págs. '+', '.join(map(str, sorted({r.page for r in [*hole.intervals,*hole.tests]}))), 'left')
    text(0, bottom+13, 'Cifras oficiales sin recalcular. Revisar avisos de discrepancia.', 'left')
    if hole.vs_bands:
        band = hole.vs_bands[0]
        text(0, bottom+19, f'Vs: figura pág. {band.page}; límites: {band.profile}, tabla pág. {band.table_page}.', 'left')
    if include_table:
        import textwrap
        cursor = bottom+28
        columns = [0, 15, 31, 48, 65, 82, 215]
        def table_row(values, row_height=6):
            nonlocal cursor
            line([0,cursor],[215,cursor])
            for i, value in enumerate(values):
                text(columns[i]+1, cursor+row_height/2, value, 'left')
            for x in columns:
                line([x,cursor],[x,cursor+row_height])
            cursor += row_height
            line([0,cursor],[215,cursor])
        table_row(['Desde m','Hasta m','Perf. m','Rec. m','Rec. %','Descripción / página'])
        for row in hole.intervals:
            lines = textwrap.wrap(row.description+f' (p. {row.page})', 75)
            table_row([row.start,row.end,row.drilled,row.recovered,row.recovery,'\n'.join(lines)], max(6,4*len(lines)+2))
        cursor += 10
        columns = [0, 15, 31, 48, 65, 82, 99, 117, 139, 155, 215]
        table_row(['N.º','Desde m','Hasta m','Hinc. m','Rec. m','N1','N2','N3','NSPT','Página'])
        for row in hole.tests:
            table_row([row.index,row.start,row.end,row.driven,row.recovered,row.n1,row.n2,row.n3,row.nspt,row.page])
        bottom = cursor
    return dict(items=scene, viewbox=[-5, -6, 310 if hole.vs_bands else 235, bottom+30], depth=depth, nspt_max=nmax)


def build_stratigraphy_lisp(hole, master_path, include_table=False):
    if not hole.reviewed:
        raise ValueError('Coteja las tablas, profundidades, discrepancias y hatch antes de insertar.')
    scene = stratigraphy_scene(hole, include_table)
    commands = []
    def pt(point):
        return f'(se:p {point[0]:.10g} {point[1]:.10g})'
    for item in scene['items']:
        kind = item['kind']
        if kind == 'line':
            commands.append(f'(se:add (vla-AddLine ms {pt(item["points"][0])} {pt(item["points"][1])}) {item["color"]})')
        elif kind == 'circle':
            commands.append(f'(se:add (vla-AddCircle ms {pt(item["point"])} (* k {item["radius"]})) {item["color"]})')
        elif kind == 'triangle':
            points = item['points']
            commands.append(f'(se:add (vla-AddSolid ms {pt(points[0])} {pt(points[1])} {pt(points[2])} {pt(points[2])}) {item["color"]})')
        elif kind == 'text':
            label = mtext_label(item['text'])
            commands.append(f'(se:text {pt(item["point"])} {lisp_string(label)} '+str({'left':4,'center':5,'right':6}[item['anchor']])+')')
        elif kind == 'hatch':
            template = HATCHES.get(item['material'])
            if not template:
                raise ValueError('Falta el hatch del master para '+item['material'])
            x1,y1,x2,y2 = item['bounds']
            commands.append(f'(se:hatch {pt([x1,y1])} {pt([x2,y2])} {lisp_string(template["pattern"])})')
    body = '\n      '.join(commands)
    patterns = ' '.join(lisp_string(HATCHES[name]['pattern']) for name in
                        dict.fromkeys(item['material'] for item in scene['items'] if item['kind'] == 'hatch'))
    master = lisp_string(str(master_path).replace('\\','/'))
    return '''(vl-load-com)
(defun c:SINCAL-ESTRATIGRAFIA (/ *error* se:p se:add se:text se:hatch se:dbx se:source se:finish doc ms db base k created grp arr oldecho undo obj result)
  (defun se:finish (status message / completion f)
    (if (and (boundp '*SINCAL_ESTRAT_COMPLETION*) *SINCAL_ESTRAT_COMPLETION*)
      (progn
        (setq completion *SINCAL_ESTRAT_COMPLETION* *SINCAL_ESTRAT_COMPLETION* nil)
        (if (setq f (open (car completion) "w"))
          (progn (write-line (cadr completion) f) (write-line status f) (write-line message f) (close f)))))
    (princ (strcat "\\n[SINCAL] " message)) (princ))
  (defun *error* (msg)
    (foreach obj created (vl-catch-all-apply 'vla-Delete (list obj)))
    (if grp (vl-catch-all-apply 'vla-Delete (list grp)))
    (if db (vl-catch-all-apply 'vlax-release-object (list db)))
    (if undo (vla-EndUndoMark doc))
    (if oldecho (setvar "CMDECHO" oldecho))
    (se:finish "error" (strcat "Estratigrafia cancelada: " (if result result msg))))
  (defun se:p (x y) (vlax-3d-point (list (+ (car base) (* k x)) (- (cadr base) (* k y)) (caddr base))))
  (defun se:add (obj color)
    (setq created (cons obj created)) (vla-put-Layer obj "0")
    (vla-put-Color obj color) (vla-put-Linetype obj "Continuous") obj)
  (defun se:dbx (/ prog candidate found)
    (foreach prog (list (strcat "ObjectDBX.AxDbDocument." (substr (getvar "ACADVER") 1 2)) "ObjectDBX.AxDbDocument" "ZWCAD.ZcDbDocument")
      (if (not found)
        (progn (setq candidate (vl-catch-all-apply 'vla-GetInterfaceObject (list (vlax-get-acad-object) prog)))
          (if (not (vl-catch-all-error-p candidate)) (setq found candidate))))) found)
  (defun se:text (pt label attachment / txt ent result)
    (setq txt (se:add (vla-AddMText ms pt (* k 220.0) label) 3))
    (vla-put-StyleName txt "RomanD") (vla-put-Height txt (* k 2.5))
    (vla-put-AttachmentPoint txt attachment) (vla-put-InsertionPoint txt pt)
    (setq ent (vlax-vla-object->ename txt))
    (setq result (vl-catch-all-apply 'setpropertyvalue (list ent "Annotative" 1)))
    (if (vl-catch-all-error-p result)
      (progn (regapp "AcadAnnotative")
        (if (not (entmod (append (entget ent) '((-3 ("AcadAnnotative" (1000 . "AnnotativeData") (1002 . "{") (1070 . 1) (1070 . 1) (1002 . "}"))))))) (exit))))
    (vl-cmdf "_.-OBJECTSCALE" ent "" "_Add" (getvar "CANNOSCALE") "")
    (vla-put-Height txt (* k 2.5)) (vla-put-InsertionPoint txt pt))
  (defun se:source (pattern / source item)
    (vlax-for item (vla-Item (vla-get-Blocks db) "PROSPECCIONES")
      (if (and (= (vla-get-ObjectName item) "AcDbHatch") (= (vla-get-PatternName item) pattern))
        (if source (progn (setq result (strcat "Hatch duplicado en master: " pattern)) (exit)) (setq source item))))
    (if (not source) (progn (setq result (strcat "Falta hatch en master: " pattern)) (exit))) source)
  (defun se:hatch (a b pattern / source objects copied sample data tail en ax ay bx by z coords boundary hatch native prefix)
    ;; Clone the master's pattern definitions; no dependency on local PAT files.
    (setq source (se:source pattern))
    (setq objects (vlax-make-safearray vlax-vbObject '(0 . 0)))
    (vlax-safearray-put-element objects 0 source)
    (setq copied (vla-CopyObjects db objects ms) sample (car (vlax-safearray->list (vlax-variant-value copied))))
    (setq created (cons sample created))
    (vla-put-PatternScale sample (* k 14.0 (vla-get-PatternScale source)))
    (setq data (entget (vlax-vla-object->ename sample)) tail (member (assoc 75 data) data))
    (setq tail (vl-remove-if-not '(lambda (p) (member (car p) '(75 76 52 41 77 78 53 43 44 45 46 79 49))) tail))
    (setq a (vlax-safearray->list (vlax-variant-value a)) b (vlax-safearray->list (vlax-variant-value b))
          ax (car a) ay (cadr a) bx (car b) by (cadr b) z (caddr a))
    ;; Let CAD construct and own a valid external loop. A hand-made HATCH loop
    ;; may display but have no computable area / persistence on some releases.
    (setq coords (vlax-make-safearray vlax-vbDouble '(0 . 7)))
    (vlax-safearray-fill coords (list ax ay bx ay bx by ax by))
    (setq boundary (se:add (vla-AddLightWeightPolyline ms coords) 8))
    (vla-put-Closed boundary :vlax-true) (vla-put-Elevation boundary z)
    (setq objects (vlax-make-safearray vlax-vbObject '(0 . 0)))
    (vlax-safearray-put-element objects 0 boundary)
    (setq hatch (vla-AddHatch ms 1 "SOLID" :vlax-false))
    (setq created (cons hatch created))
    (vla-AppendOuterLoop hatch objects)
    (vla-Evaluate hatch)
    (setq en (vlax-vla-object->ename hatch) native (entget en) prefix nil)
    (while (and native (/= (caar native) 75))
      (setq prefix (cons (car native) prefix) native (cdr native)))
    (setq prefix (reverse prefix))
    (setq prefix (subst (assoc 2 data) (assoc 2 prefix) prefix)
          prefix (subst (assoc 70 data) (assoc 70 prefix) prefix))
    (if (not (entmod (append prefix tail '((98 . 0))))) (progn (princ "No se pudo aplicar el patron master") (exit)))
    (vla-put-Layer hatch "0") (vla-put-Color hatch 8)
    (vla-Evaluate hatch)
    (vla-Delete boundary) (setq created (vl-remove boundary created))
    (vla-Delete sample) (setq created (vl-remove sample created)))
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)) ms (vla-get-ModelSpace doc))
  (cond
    ((/= (getvar "INSUNITS") 6) (se:finish "error" "Estratigrafia requiere metros (INSUNITS=6)."))
    ((= (getvar "CVPORT") 1) (se:finish "error" "Activa Model antes de insertar."))
    ((/= 0 (logand 5 (cdr (assoc 70 (tblsearch "LAYER" "0")))) ) (se:finish "error" "Desbloquea y descongela la capa 0."))
    (T
      (setq db (se:dbx))
      (if (not db) (progn (setq result "No se pudo abrir el master instalado en lectura") (exit)))
      (vla-Open db MASTER_PATH)
      ;; Validate every required pattern before prompting or creating entities.
      (foreach obj (list REQUIRED_PATTERNS) (se:source obj))
      (vla-Item (vla-get-TextStyles db) "RomanD")
      (setq base (getpoint "\\nPunto superior izquierdo de la estratigrafia: "))
      (if base
        (progn
          (setq base (trans base 1 0) k (/ 1.0 (getvar "CANNOSCALEVALUE")) oldecho (getvar "CMDECHO"))
          (vla-StartUndoMark doc) (setq undo T) (setvar "CMDECHO" 0)
          (if (not (tblsearch "STYLE" "RomanD"))
            (progn (setq arr (vlax-make-safearray vlax-vbObject '(0 . 0)))
              (vlax-safearray-put-element arr 0 (vla-Item (vla-get-TextStyles db) "RomanD"))
              (vla-CopyObjects db arr (vla-get-TextStyles doc))))
          SCENE_BODY
          (setq grp (vla-Add (vla-get-Groups doc) "GROUP_NAME"))
          (setq arr (vlax-make-safearray vlax-vbObject (cons 0 (1- (length created)))))
          (vlax-safearray-fill arr (reverse created)) (vla-AppendItems grp arr)
          (vla-EndUndoMark doc) (setq undo nil) (setvar "CMDECHO" oldecho)
          (vlax-release-object db) (setq db nil) (vla-Regen doc 1)
          (se:finish "ok" "Estratigrafia vectorial insertada. Valores oficiales conservados."))
        (progn (vlax-release-object db) (setq db nil) (se:finish "cancelled" "Insercion cancelada sin elegir un punto.")))))
  (princ))
'''.replace('MASTER_PATH', master).replace('REQUIRED_PATTERNS', patterns).replace('SCENE_BODY', body).replace('GROUP_NAME', 'SINCAL_ESTRAT_'+uuid.uuid4().hex)
