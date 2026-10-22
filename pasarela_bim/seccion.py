"""Canto por tramo: un descanso sólo modifica la cara superior de la viga."""
import math


def _numero(valor):
    try:
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    except OverflowError:
        return False


def familia_del_tramo(familia, tramo, nodos):
    if familia.get('tipo') == 'escalera':
        return familia
    perfil = tramo.get('rasante', [])
    numero = _numero
    if not isinstance(perfil,list) or len(perfil)<3 or not all(isinstance(p,dict) and numero(p.get('t')) and numero(p.get('f')) for p in perfil):
        return familia
    if not any(b['t']>a['t'] and abs(b['f']-a['f'])<1e-10 and 0<a['f']<1 for a,b in zip(perfil,perfil[1:])):
        return familia
    referencias = [tramo.get('desde'), tramo.get('hasta')]
    if not all(isinstance(ref, str) for ref in referencias):
        return familia
    a,b=(nodos.get(ref) for ref in referencias)
    if not a or not b or not all(numero(n.get(k)) for n in (a,b) for k in 'xyz') or not numero(familia.get('canto_mm')):
        return familia
    largo=math.hypot(b['x']-a['x'],b['y']-a['y'])
    dz=b['z']-a['z']
    if not numero(largo) or not numero(dz) or largo<=0 or abs(dz)<1e-7:
        return familia
    if any(b['t']<=a['t'] or (b['f']>a['f'] and abs(abs(dz)*(b['f']-a['f'])/(largo*(b['t']-a['t']))-.08)>1e-8) for a,b in zip(perfil,perfil[1:])):
        return familia
    # The editable depth belongs to the upper ramp. Intrados runs at 8%.
    cantos=[{'t':p['t'],'canto_mm':familia['canto_mm']+.08*largo*(1-p['t'] if dz>0 else p['t'])-abs(dz)*(1-p['f'] if dz>0 else p['f'])} for p in perfil]
    return {**familia,'perfil_canto':cantos,'canto_fin_mm':cantos[-1]['canto_mm'],'canto_por_descanso':True}
