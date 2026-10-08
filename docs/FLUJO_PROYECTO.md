# Menú y flujo de Proyecto

El menú lateral usa íconos y esta jerarquía, sin numeración:

- Home
- Documentación
- Proyecto: carga común de archivos locales y JSON del puente.
  - Archivo: Renombrado y Conversión DXF–DWG.
  - Propiedades: DWGPROPS.
  - Revisiones: Editor de revisiones y Nueva revisión.
  - Prospecciones: Estratigrafía y Perfiles geofísicos.
  - Mapa de ubicación.
- Comandos en vivo
- Generador de armadura
  - Estribos: entrada y salida.
  - Viga.
  - Cepa, cuando corresponde.
  - Travesaño: sobre apoyos e intermedio.
  - Losa.
- Consulta de proyecto
- Diagnóstico: soporte, motores, integración y conexión AutoCAD / ZWCAD.

## Archivos compartidos

- Incorpora informes PDF/TXT, KML/KMZ, DWG, DXF, carpetas y documentos de referencia en Proyecto.
- Proyecto centraliza los archivos generales y reconocimientos guardados de estratigrafía. Como excepción, la página inicial del Generador de armadura permite incorporar el JSON del puente y las memorias PDF/Excel. El JSON se comparte con Consulta.
- Cuando una herramienta solicita archivos, muestra solo los compatibles ya incorporados al proyecto. Puedes elegir un subconjunto; si faltan archivos, añádelos desde Proyecto. Las herramientas no abren selectores de archivos del equipo.
- Incorporar un informe no inicia OCR ni modifica planos. Cada herramienta mantiene su confirmación, vista previa y protecciones de guardado.
- Las carpetas de salida se eligen explícitamente: no se reutiliza automáticamente la carpeta de entrada.
- Los documentos de referencia (Office, imágenes, CSV, ZIP, IFC y RVT) se registran como referencias, no se interpretan ni ejecutan.
- La lista contiene referencias a rutas locales, no copias: no sube archivos a Internet ni los conserva entre aperturas de SINCAL. Quitar una referencia no borra el archivo.
- Renombrar o mover un archivo fuera de la herramienta puede invalidar su referencia; vuelve a seleccionarlo si cambió de ruta.

## Inicio del Generador de armadura

- Incluye carga del JSON, referencias a memorias PDF/Excel y una guía breve del flujo.
- Las memorias no se interpretan, ni se ejecutan macros o fórmulas; el análisis está pendiente. Se admiten PDF y Excel XLS/XLSX/XLSM.
- Estribos conserva sus herramientas de entrada y salida. Travesaño conserva los generadores existentes de cuadrantes y despieces; sus configuraciones específicas sobre apoyos e intermedia siguen pendientes.
- Viga, Cepa y Losa tienen páginas identificadas como pendientes, sin cálculos ni generación CAD nuevos.
- Las memorias permanecen en la lista mientras esté abierta la aplicación; Descartar proyecto también limpia estas referencias, nunca los originales.
