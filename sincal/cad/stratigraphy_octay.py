"""Puerto Octay layout: documentary SPT intervals, not an interpolated curve."""
import math
import textwrap

from sincal.prospecciones import number
from sincal.stratigraphy_hatches import HATCHES
from sincal.cad.stratigraphy import append_tables, drawing_label


def interval_scene(hole, include_table=False):
    items = []
    def line(a, b, color=8, **metadata):
        items.append(dict(kind='line', points=[a,b], color=color, **metadata))
    def text(x, y, label, anchor='center', **metadata):
        items.append(dict(kind='text', point=[x,y], text=drawing_label(label),
                          anchor=anchor, color=3, height=2.5, **metadata))

    soil_depth = max(number(r.end) for r in hole.strata)
    drilled_depth = max(soil_depth, *(number(r.end) for r in hole.samples))
    depth = max(drilled_depth, *(number(b.end) for b in hole.vs_bands)) if hole.vs_bands else drilled_depth
    labels = [textwrap.wrap(f'{r.method}: '+(r.description or f'Sin descripción recuperada (pág. {r.page})'), 68)
              for r in hole.samples]
    # Fixed paper text height; expand the depth scale when dense/long labels need it.
    height = max(210, depth*12, sum(max(4,len(lines)*4)+1.5 for lines in labels)+12)
    top, gx, width, rx, rw = 27, 38, 80, 280, 50
    def y(value):
        return top+number(value)*height/depth
    nmax = max(100, math.ceil(max((number(t.nspt) for t in hole.tests if not t.refusal), default=0)/10)*10)
    text(0,0,f'Sondaje {hole.name}','left')
    text(0,7,'Formato Puerto Octay · ensayos por intervalo','left')
    text(0,19,'Prof. (m)','left')
    text(gx+width/2,14,'NSPT (golpes/pie)')
    text(141,14,'Descripción por muestra','left')
    text(rx+rw/2,14,'Recuperación (%)')
    for start, span, maximum in [(gx,width,nmax),(rx,rw,100)]:
        for i in range(11):
            xx=start+span*i/10
            line([xx,top],[xx,y(drilled_depth)])
            if start==gx or i%2==0:
                text(xx,23,f'{maximum*i/10:g}')
                line([xx,top-2],[xx,top],1)
    step=max(1,math.ceil(depth/40))
    for d in sorted(set([*range(0,math.ceil(depth),step),depth])):
        yy=y(d)
        if d<=drilled_depth:
            line([gx,yy],[gx+width,yy]);line([rx,yy],[rx+rw,yy])
        line([9,yy],[12,yy],1)
        if d==depth or depth-d>=step*.45:
            text(7,yy,f'{d:g}','right')
    for row in hole.strata:
        a,b=y(row.start),y(row.end)
        for name in [row.material,*row.inclusions]:
            items.append(dict(kind='hatch', bounds=[12,a,26,b], material=name,color=8))
        for u,v in [([12,a],[26,a]),([12,b],[26,b]),([12,a],[12,b]),([26,a],[26,b])]:
            line(u,v,1)

    for test in hole.tests:
        a,b=y(test.start),y(test.end)
        if test.refusal:
            # Outside the numeric grid: R is never an invented 80/100 value.
            if b>a: line([124,a],[124,b],1,series='refusal',test=test.index)
            else: line([123,a],[125,a],1,series='refusal',test=test.index)
            text(127,(a+b)/2,'R','left')
        else:
            xx=gx+width*number(test.nspt)/nmax
            if b>a: line([xx,a],[xx,b],5,series='nspt',test=test.index)
            else: line([xx-.7,a],[xx+.7,a],5,series='nspt',test=test.index)

    previous=None
    for row in hole.samples:
        a,b=number(row.start),number(row.end)
        if b<=a: continue
        xx=rx+rw*number(row.recovery)/100
        if previous and abs(a-previous[1])<.011:
            line([previous[0],y(a)],[xx,y(a)],5,series='recovery')
        line([xx,y(a)],[xx,y(b)],5,series='recovery')
        previous=(xx,b)

    last_bottom=top-3
    for row,lines in zip(hole.samples,labels):
        centre=(y(row.start)+y(row.end))/2
        half=max(2,2*len(lines))
        yy=max(centre,last_bottom+1.5+half)
        text(141,yy,'\n'.join(lines),'left',sample=row.index)
        if yy-centre>.2:
            line([135,centre],[139,yy],8,series='description-leader')
        last_bottom=yy+half

    if hole.vs_bands:
        text(367,14,'Vs (m/s)')
        for band in hole.vs_bands:
            a,b=y(band.start),y(band.end);mid=(a+b)/2
            line([343,a],[391,a],1);line([343,b],[391,b],1)
            line([367,a],[367,mid-2],1);line([367,mid+2],[367,b],1)
            for tip,inside in [(a,a+1.6),(b,b-1.6)]:
                items.append(dict(kind='triangle',points=[[367,tip],[366.4,inside],[367.6,inside]],color=1))
            text(367,mid,band.label)

    bottom=max(y(depth),last_bottom)+10
    text(0,bottom,'Azul: NSPT medido por intervalo. R: rechazo, sin equivalencia numérica.','left')
    text(0,bottom+6,'NSPT corregido: no extraído; no se calcula ni se copia de otro plano.','left')
    text(0,bottom+12,'Recuperación en panel independiente. Textos desplazados: guía al intervalo original.','left')
    if hole.water_depth:
        text(0,bottom+18,f'Napa: {hole.water_depth} m (pág. {hole.water_page})','left')
    bottom+=27
    for name in dict.fromkeys(n for r in hole.strata for n in [r.material,*r.inclusions]):
        items.append(dict(kind='hatch',bounds=[0,bottom,14,bottom+5],material=name,color=8))
        text(18,bottom+2.5,HATCHES[name]['label'],'left');bottom+=8
    if soil_depth<drilled_depth:
        text(0,bottom+3,f'Horizontes hasta {soil_depth:g} m; sin extrapolar.','left');bottom+=7
    pages=sorted({r.page for r in [*hole.strata,*hole.samples,*hole.tests,*hole.vs_bands]})
    text(0,bottom+3,'Fuente: tablas del informe, págs. '+', '.join(map(str,pages)),'left')
    bottom+=12
    if include_table: bottom=append_tables(hole,bottom+10,line,text)
    return dict(items=items,viewbox=[-5,-6,410 if hole.vs_bands else 345,bottom+15],depth=depth,
                nspt_max=nmax,format=hole.drawing_format,depth_scale=height/depth,depth_origin=top,
                accessible_label='Puerto Octay: NSPT por intervalo, rechazo, descripciones, estratos y recuperación separada')
