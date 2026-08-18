# 🏛️ SINCAL - Suite de Ingeniería y Estándares CAD

**SINCAL Suite 1.0** es una aplicación para Windows orientada a unificar estándares de dibujo (AutoCAD/ZWCAD), automatizar tareas repetitivas de ingeniería estructural y generar apoyo gráfico de ubicación a partir de archivos `.kmz`. La generación del producto se mantiene como 1.0; la secuencia técnica de distribución continúa en `v28.0.1` para que las instalaciones históricas v27 detecten correctamente la migración.

---

## 🚀 Características Principales

* **Distribución por instalador firmado:** El ejecutable y los recursos se entregan como una instalación local autocontenida.
* **Integración CAD local:** Prepara un cargador confiable en `%APPDATA%\Estandar SINCAL` para AutoCAD/ZWCAD y mantiene allí los recursos CAD activos.
* **Actualizaciones menores desde un canal público separado:** Detecta automáticamente LISPs nuevos o editados, scripts, estilos, mapas y el master DWG publicados en `drossull/sincal-updates`. Cada archivo se limita por tipo y tamaño y se valida contra el SHA del blob de Git antes de activarlo.
* **Vista previa integrada en AutoCAD 2025:** El instalador incluye una primera pestaña Ribbon SINCAL y una paleta acoplable de prueba. La aplicación de escritorio sigue siendo la interfaz funcional principal durante la migración.
* **Procesamiento Masivo Nativo (PowerShell):** Permite procesar decenas de planos de golpe directamente desde la carpeta de Windows sin abrir AutoCAD.
* **Módulo Estructural (BIM 2D):** Generación inteligente de vistas de armaduras (Zapatas, Consolas, Muros), dibujo y despiece paramétrico, inyección de cotas matemáticas, y lectura de parámetros desde archivos JSON de proyecto.
* **Generador de Croquis de Ubicación:** Lector nativo de archivos `.kmz` (Google Earth) que usa mapas MOP calibrados disponibles localmente para generar un PNG de apoyo.
* **Comandos en Vivo (Conexión COM):** Ejecuta comandos de forma remota en AutoCAD directamente desde la interfaz del programa.
* **Renombrado Avanzado:** Herramienta de interfaz para buscar, reemplazar y actualizar revisiones de planos DWG de forma masiva en milisegundos.
* **Documentación (Wiki):** Biblioteca interactiva integrada con todos los comandos y manuales.

---

## 💻 Guía de Uso Rápido

1. **Instala SINCAL:** Usa el instalador oficial `Setup_SINCAL_*.exe`.
2. **Ejecuta SINCAL:** La aplicación ya no necesita elevarse globalmente para iniciar.
3. **Preparación CAD:** Ve a la pestaña "Sincronizador" y haz clic en **"Preparar integración CAD"** si necesitas regenerar el wrapper o los archivos de arranque local.
4. **Actualizar estándares:** SINCAL consulta automáticamente los recursos CAD al iniciar y muestra un aviso si existen cambios. También puedes usar **"Actualizar recursos CAD"** para comprobarlos manualmente.
5. **Módulos Activos:** * Visita la pestaña **"Módulo Estructural"** para detallar encapados y generar despieces.
   * Visita la pestaña **"Ubicación"** para generar mapas regionales georreferenciados.

### Flujo para publicar un recurso CAD

1. Agrega o edita el archivo dentro de una carpeta autorizada: `lisps`, `startup`, `scripts`, `plotstyles`, `mapas` o el master `masters/FORMATOS ANOTATIVOS ACAD_2025.dwg`.
2. Valida el recurso localmente. Para el master, guarda una copia de respaldo y comprueba bloques, atributos y referencias externas con AutoCAD.
3. Haz commit y push a la rama `main` del repositorio privado de desarrollo. El workflow `publish-distribution.yml` exporta únicamente la lista blanca a `drossull/sincal-updates`; un LISP nuevo no necesita incorporarse manualmente a un manifiesto.
4. Al abrir SINCAL, acepta el aviso de actualización. Los archivos se guardan en `%LOCALAPPDATA%\SINCAL\resources` y los recursos CAD activos se materializan en `%APPDATA%\Estandar SINCAL`.
5. Cierra y vuelve a abrir SINCAL para refrescar la interfaz. SINCAL intenta recargar automáticamente los LISPs en dibujos CAD abiertos; si el host no permite la recarga, abre un dibujo nuevo o reinicia AutoCAD/ZWCAD.

La sincronización no reemplaza `SINCAL.exe`, Python ni el plugin .NET. Esos cambios requieren un instalador oficial desde Releases. Como los LISPs y scripts sí son código ejecutable, la rama `main` debe tener protección, revisión y acceso de escritura limitado. La primera versión que incorpora este sistema debe instalarse una vez de manera convencional; las actualizaciones menores posteriores ya no requieren reinstalación.

El repositorio de desarrollo puede permanecer privado. El repositorio público de distribución no recibe código Python, fuentes .NET, archivos de proyecto ni secretos; `tools/export_distribution.py` aplica la misma política de rutas que el cliente y genera un manifiesto auditable.

### Preparar un entorno de compilación

```powershell
python -m pip install -r requirements-build.txt
pwsh -NoProfile -File tools/build_release.ps1
```

El script valida Python, PowerShell, pruebas unitarias, plugin .NET, ejecutable, instalador, firma y checksums. Usa `-SkipSigning` únicamente para una compilación local de prueba.

---

## ⚙️ Uso de Comandos Masivos (PowerShell)

SINCAL utiliza **PowerShell 7** para procesar docenas de planos `.dwg` a la vez. No necesitas abrir AutoCAD.

1. Abre la carpeta de Windows donde están tus planos.
2. Haz clic en la barra de direcciones superior (donde sale la ruta).
3. Borra el texto, escribe `cmd` y presiona **Enter**.
4. En la ventana negra, escribe directamente el nombre de la herramienta (ej. `PURGEALL`, `PAGESETUP-A1`, `PUBLISH`) y presiona **Enter**.
