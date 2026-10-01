"""Interface-specific guidance without changing the installed Tk manual."""
import json
from pathlib import Path
from sincal.runtime import ruta_recurso

OVERRIDES = {
    'primer-inicio': 'Esta vista previa funciona en una ventana de escritorio con WebView2. No requiere abrir un navegador ni publicar un sitio. Consulta, sesiones, documentación y cálculo trabajan localmente. Internet se usa para comprobar/descargar recursos. La edición instalada anterior no se sustituye hasta compilar y validar el nuevo instalador.',
    'actualizaciones': 'En Home → Sincronizador pulsa Comprobar recursos. Revisa el manifiesto y aplica la actualización cuando lo decidas. No se instala una release automáticamente. La preparación CAD materializa los recursos y registra rutas para tu usuario; requiere reiniciar CAD.',
    'interfaz-accesibilidad': 'El selector conserva Oscuro, Claro y Sistema, además de las paletas Cadence. Texto permite 90 %, 100 % o 115 %. Los dos controles superiores ocultan independientemente el menú izquierdo y el índice derecho. Los márgenes centrales se conservan. La selección del menú se indica con texto resaltado y una línea, no con un fondo coloreado. Las preferencias se guardan localmente.',
    'procesamiento-general': 'Trabaja sobre una copia de seguridad. Renombrado prepara una lista exacta antes de tocar archivos. La vista previa rechaza colisiones y revalida tamaño y fecha antes de aplicar. No recorre subcarpetas. Los scripts masivos existentes siguen disponibles desde CMD con su motor seleccionado y sus propios registros.',
    'renombrado': 'Elige carpeta, escribe Buscar y Reemplazar por, y pulsa Preparar cambios. Verifica cada nombre y confirma Aplicar estos cambios. Se conservan las extensiones; no se sobrescriben archivos. Ante un fallo se intenta revertir los renombrados ya realizados sin pisar otros archivos.',
    'conversion-dxf': 'Selecciona los DXF y una carpeta de salida. Cierra AutoCAD y ZWCAD, elige motor y confirma Convertir. Se crea una instancia temporal y DWG nuevos: los DXF no se modifican. Se rechazan destinos existentes o repetidos. Una cancelación deja de esperar; no mata CAD y puede quedar una conversión en curso.',
    'comandos-vivo': 'Escribe un nombre de comando y pulsa Enter o Ejecutar. Por defecto se usa el dibujo activo. Puedes activar Todos los dibujos abiertos y confirmar la lista: se recorren uno a uno, deteniéndose al fallar o cambiar los destinos. El glosario explica qué modifica cada orden. Un comando puede guardar o exportar por sí mismo. Los personalizados necesitan la confirmación de que no piden pasos adicionales. No se aceptan parámetros ni LISP libre. Ante un resultado incierto no se reenvía automáticamente.',
    'sesiones-armaduras': 'Guardar sesión crea una instantánea privada del usuario de Windows con JSON, identificación, ambos estribos, travesaños e informe de prospecciones. Sesiones permite buscar, cargar, importar archivos anteriores y exportar una copia. El original importado no se modifica. Los handles CAD no se reactivan: vuelve a detectar moldajes. Cada 60 segundos se guarda una recuperación de cambios pendientes; al abrir se ofrece recuperarla o cargar la última sesión guardada. Usuarios que compartan una cuenta Windows comparten estos datos.',
    'diagnostico-soporte': 'Generar diagnóstico prepara un resumen y ZIP redactado sin adjuntar DWG. Puedes descargarlos y revisarlos antes de compartirlos. Detectar motores instalados permite seleccionar el motor de los scripts por carpeta. Home → Historial permite descargar un registro por operación, conservado por 30 días con máximo 100 archivos. Los temporales internos de operaciones vencen a los 7 días; no se limpian dibujos ni sesiones guardadas.',
    'solucion-problemas': 'Si CAD no responde, comprueba que esté abierto, con el dibujo correcto y sin comandos o diálogos pendientes. Varias instancias bloquean la selección automática. Si una orden queda esperando, revisa la línea de comandos CAD antes de repetir. Un resultado de ejecución terminado confirma el retorno de control, no certifica el contenido del dibujo. Usa Home → Historial para el registro y Diagnóstico para un informe de entorno.',
}


def documentation():
    data = json.loads(Path(ruta_recurso('tutoriales.json')).read_text(encoding='utf-8'))
    data['temas'] = [topic for topic in data['temas'] if 'sesion' not in topic['id']]
    for topic in data['temas']:
        if topic['id'] in OVERRIDES:
            topic['contenido'] = OVERRIDES[topic['id']]
        elif topic['id'] == 'modulo-estructural':
            topic['contenido'] = topic['contenido'].replace(
                'A la izquierda está Revisión y marcas; a la derecha, una página desplazable reúne Zapata, Muros, Consolas, Topes y Contrafuerte.',
                'La página central reúne dimensiones, reglas, marcas y envío CAD. TRAVESAÑOS aparece como sección independiente. Los componentes aún sin lógica definida no se generan.')
        topic['contenido'] = topic['contenido'].replace('Consulta, sesiones, documentación y cálculo', 'Consulta, documentación y cálculo')
    return data
