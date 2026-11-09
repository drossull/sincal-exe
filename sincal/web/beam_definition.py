"""Local reference samples for discussing beam shapes, not a rebar generator.

The photographed shapes are available only for the H200 being discussed.
They share a transverse station to compare their shapes. Physical coordination
between families and longitudinal distribution remain open.
No schedules, CAD entities or project modifications are produced here.
"""
import math

def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def scale(a,s): return tuple(x*s for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a): return math.hypot(*a)
def unit(a): return scale(a,1/norm(a))


def fillet_path(raw, diameter):
    """Real spatial circular fillets; dimensions remain in metres."""
    radius=3*diameter/1000
    points=[tuple(p) for p in raw]
    arcs=[]
    for a,b,c in zip(points,points[1:],points[2:]):
        incoming,outgoing=unit(sub(b,a)),unit(sub(c,b))
        angle=math.acos(max(-1.,min(1.,dot(incoming,outgoing))))
        assert 1e-9<angle<math.pi-1e-9
        normal=unit(cross(incoming,outgoing));reach=radius*math.tan(angle/2)
        start,end=sub(b,scale(incoming,reach)),add(b,scale(outgoing,reach))
        center=add(start,scale(cross(normal,incoming),radius))
        assert abs(norm(sub(end,center))-radius)<1e-9
        arcs.append(dict(type='arc',start=start,end=end,center=center,normal=normal,
                         radius_m=radius,sweep_radians=angle,length_m=radius*angle))
    segments=[];cursor=points[0]
    for i,arc in enumerate(arcs):
        vector=sub(arc['start'],cursor)
        assert dot(vector,unit(sub(points[i+1],points[i])))>=-1e-9
        if norm(vector)>1e-10:
            segments.append(dict(type='line',start=cursor,end=arc['start'],length_m=norm(vector)))
        segments.append(arc);cursor=arc['end']
    vector=sub(points[-1],cursor)
    assert dot(vector,unit(sub(points[-1],points[-2])))>=-1e-9
    if norm(vector)>1e-10:
        segments.append(dict(type='line',start=cursor,end=points[-1],length_m=norm(vector)))
    return segments



def _sample_segments(segments):
    points=[tuple(segments[0]['start'])]
    for segment in segments:
        if segment['type']=='line':
            points.append(tuple(segment['end']))
            continue
        center=segment['center'];radial=sub(segment['start'],center)
        tangent=cross(segment['normal'],radial)
        steps=max(2,math.ceil(abs(segment['sweep_radians'])/math.radians(.5)))
        for index in range(1,steps+1):
            angle=segment['sweep_radians']*index/steps
            points.append(add(center,add(scale(radial,math.cos(angle)),scale(tangent,math.sin(angle)))))
        if math.dist(points[-1],segment['end'])>1e-9:
            raise ValueError('No coincide la tangencia de la muestra de armadura.')
    return points


def _upper_return_segments(station, height, shoulder_slope, shoulder_intercept,
                           diameter, cover, tail):
    """Return the symmetric H200 bar tangent to both flange cover limits (m)."""
    radius = 3 * diameter
    axis_cover = cover + diameter / 2
    top = height - axis_cover
    middle = top - radius
    bottom = top - 2 * radius
    # Perpendicular distance from the bend centre to the sloping underside
    # must include the bend radius, bar radius and concrete cover.
    clearance = (radius + axis_cover) * math.hypot(1, shoulder_slope)
    half_run = (middle - shoulder_intercept - clearance) / shoulder_slope

    def straight(start, end):
        return dict(type='line', start=start, end=end, length_m=math.dist(start, end))

    def half_turn(x, start_z, end_z):
        return dict(type='arc', start=(x, station, start_z), end=(x, station, end_z),
                    center=(x, station, middle), normal=(0, 1, 0),
                    radius_m=radius, sweep_radians=math.pi, length_m=math.pi * radius)

    return [
        straight((-half_run + tail, station, bottom), (-half_run, station, bottom)),
        half_turn(-half_run, bottom, top),
        straight((-half_run, station, top), (half_run, station, top)),
        half_turn(half_run, top, bottom),
        straight((half_run, station, bottom), (half_run - tail, station, bottom)),
    ]


def build_definition(profile, scene, slope):
    """Return a clearly scoped reference for the selected beam specimen."""
    result=dict(available=False,bars=[],issues=[],cover_cm=2.5,
                scope='Muestra de armaduras en una misma sección; reparto y encuentros pendientes.',
                fabrication_ready=False,distribution_defined=False)
    if not scene:
        result['issues'].append('No hay un tramo interior disponible para la muestra.')
        return result
    if profile.get('type')!=6 or profile.get('source')!='catalog':
        result['issues'].append('Las formas de referencia están definidas sólo para la H200.')
        return result
    p=profile['parameters_mm'];cover=.025
    length=scene['specimen_length_m'];station=length/2
    if length<=.04:
        result['issues'].append('El tramo disponible no alcanza para representar los cierres de muestra.')
        return result
    bars=[]
    alpha=math.atan(-slope)
    transform=lambda point:(point[0],point[1]*math.cos(alpha)-point[2]*math.sin(alpha),
                             point[1]*math.sin(alpha)+point[2]*math.cos(alpha))
    upper=p['b1']/2000;height=p['d7']/1000;lower=p['b7']/2000
    def add_segments(mark,name,diameter,native,notes):
        points=_sample_segments(native)
        bars.append(dict(id=f'beam-reference:{mark}',mark=str(mark),name=name,
                         diameter_mm=diameter,radius_m=diameter*.003,
                         local_points=points,points=[transform(pt) for pt in points],
                         native_segments=native,notes=notes,layout='common_section_reference',station_m=station,
                         fabrication_ready=False,distribution_defined=False))

    def add_bar(mark,name,diameter,raw,notes):
        add_segments(mark,name,diameter,fillet_path(raw,diameter),notes)

    # M1: the shallow V is parallel to the outer underside of the top flange.
    # Ends continue above the beam into the slab, as shown by the section photo.
    d=.008;r=3*d;c=cover+d/2;y=station;x=upper-c
    upper_outer_slope=(p['d2']/1000)/(p['b2']/1000)
    intercept=height-p['d1']/1000-upper_outer_slope*upper
    zmid=intercept+c*math.hypot(1,upper_outer_slope)
    zend=zmid+upper_outer_slope*x;ztop=zend+.23
    add_bar(1,'Estribo del ala superior',8,
            [(-x+.12+r,y,ztop),(-x,y,ztop),(-x,y,zend),(0,y,zmid),
             (x,y,zend),(x,y,ztop),(x-.12-r,y,ztop)],
            ['Forma de la foto adaptada al contorno H200.',
             'Ganchos rectos de muestra de 12 cm; pendientes de fijar al parametrizar.',
             'Ramas superiores de muestra: 23 cm entre esquinas teóricas.'])

    # M2: parallel to the steeper inner transition of the top flange.
    y=station;inner_slope=p['d3']/p['b3']
    web_top=height-(p['d1']+p['d2']+p['d3'])/1000
    zmid=web_top-inner_slope*p['b4']/2000+c*math.hypot(1,inner_slope)
    end_x=.30;end_z=zmid+inner_slope*end_x
    angle=math.pi-math.atan(inner_slope);reach=r*math.tan(angle/2)
    add_bar(2,'V de la transición superior',8,
            [(-end_x+.17+reach,y,end_z),(-end_x,y,end_z),(0,y,zmid),
             (end_x,y,end_z),(end_x-.17-reach,y,end_z)],
            ['Forma de la foto adaptada a la transición del perfil.',
             'Retornos rectos de muestra de 17 cm; largo final pendiente.'])

    # M3 uses the approved green fit, with the two returns below the top run.
    upper_return = _upper_return_segments(station, height, upper_outer_slope,
                                          intercept, .008, cover, .08)
    add_segments(3, 'Transversal superior con retornos', 8, upper_return,
                 ['Retornos de 180° hacia el centro por debajo del tramo superior.',
                  'Pata recta de muestra de 8 cm en ambos extremos.'])
    bars[-1]['upper_cover_m'] = cover

    # M6: the upper diagonals follow the offset outer shoulder of the lower bulb.
    # Its two end legs pass at distinct depth levels; one bar remains continuous.
    d=.010;r=3*d;c=cover+d/2;y=station-d/2;delta=d
    x=lower-c;bottom=c;side_slope=p['d5']/p['b5']
    intercept=p['d6']/1000+side_slope*lower-c*math.hypot(1,side_slope)
    corner_z=intercept-side_slope*x
    # Each upper leg follows one face of the web. Cover is measured to the
    # steel surface, so its axis is inset by cover plus the actual bar radius.
    web_half=p['b4']/2000
    crossed=web_half-cover-d/2
    assert crossed>d/2,'Las patas del bulbo no caben con el recubrimiento elegido.'
    peak_z=intercept+side_slope*crossed
    turn=math.pi/2-math.atan(side_slope);reach=r*math.tan(turn/2)
    end_z=peak_z+reach+.26
    add_bar(6,'Estribo del bulbo inferior',10,
            [(crossed,y,end_z),(crossed,y,peak_z),(-x,y,corner_z),(-x,y,bottom),
             (x,y+delta,bottom),(x,y+delta,corner_z),(-crossed,y+delta,peak_z),(-crossed,y+delta,end_z)],
            ['Contorno adaptado al bulbo H200 y recubrimiento de 2,5 cm.',
             'Patas superiores junto a ambas caras del alma, con recubrimiento a superficie.',
             'Patas superiores de muestra: 26 cm rectos, según la referencia.',
             'Cierre de muestra separado por su diámetro en profundidad.'])
    bulb=bars[-1]
    bulb['web_leg_placement']={
        'web_width_m':2*web_half,'axis_x_m':[-crossed,crossed],
        'axis_separation_m':2*crossed,'clear_separation_m':2*crossed-d,
        'surface_cover_m':web_half-crossed-d/2,
        'straight_leg_length_m':.26,
    }
    assert abs(bulb['web_leg_placement']['surface_cover_m']-cover)<1e-10
    for leg in (bulb['native_segments'][0],bulb['native_segments'][-1]):
        assert leg['type']=='line' and abs(leg['length_m']-.26)<1e-9
        assert abs(abs(leg['start'][0])-crossed)<1e-9
        assert abs(leg['start'][0]-leg['end'][0])<1e-9

    # M7: inverted V, parallel to the inner lower shoulder. No invented hooks.
    y=station;inner_lower=p['d4']/p['b6']
    ztop=(p['d6']+p['d5']+p['d4'])/1000+inner_lower*p['b4']/2000-c*math.hypot(1,inner_lower)
    end_x=.20;end_z=ztop-inner_lower*end_x
    add_bar(7,'V invertida del bulbo',10,
            [(-end_x,y,end_z),(0,y,ztop),(end_x,y,end_z)],
            ['Forma sin ganchos según la fotografía.',
             'Recorrido paralelo a la transición inferior del perfil.'])

    # M11: narrow tall hoop. The photographed 205 cm straight-side dimension is
    # a reference, not the 200 cm concrete height. The closure lies in the slab.
    d=.018;r=3*d;c=cover+d/2;y=station-d/2
    half_width=.055;bottom=c;top=bottom+2.05
    q=(half_width,top);center=(q[0]-r,q[1]-r)
    reach=r*math.tan(math.radians(67.5));h=(-math.sqrt(.5),-math.sqrt(.5))
    virtual_start=(center[0]+reach,top)
    virtual_end=(half_width,center[1]+reach)
    first=add(virtual_start,scale(h,reach+.11));last=add(virtual_end,scale(h,reach+.11))
    path=[first,virtual_start,(-half_width,top),(-half_width,bottom),
          (half_width,bottom),virtual_end,last]
    depths=[y,y,y,y+d,y+d,y+d,y+d]
    # Mirror the closure to the upper-left corner, as in the reference photo.
    add_bar(11,'Estribo alto del alma',18,
            [(-x,depth,z) for (x,z),depth in zip(path,depths)],
            ['205 cm y 11 cm: dimensiones de referencia de la fotografía.',
             'Cierre de muestra con patas paralelas de 11 cm y arcos 3Ø, por revisar.',
             'Los dos arcos del cierre tienen distinto plano, a 18 mm entre ejes.'])


    result.update(available=True,bars=bars,station_m=station,specimen_length_m=length,
                  issues=['Las ramas superiores se prolongan hacia la losa, no representada en esta vista.'],
                  validation={'bulb_web_leg_placement':bulb['web_leg_placement']})
    return result
