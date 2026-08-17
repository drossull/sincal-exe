# 🏛️ SINCAL - Suite de Ingeniería y Estándares CAD

**SINCAL Suite 1.0** es una aplicación para Windows orientada a unificar estándares de dibujo (AutoCAD/ZWCAD), automatizar tareas repetitivas de ingeniería estructural y generar apoyo gráfico de ubicación a partir de archivos `.kmz`.

---

## 🚀 Características Principales

* **Distribución por instalador firmado:** El ejecutable y los recursos se entregan como una instalación local autocontenida.
* **Integración CAD local:** Prepara archivos auxiliares locales para trabajar con AutoCAD/ZWCAD sin ejecutar código descargado en caliente.
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
4. **Módulos Activos:** * Visita la pestaña **"Módulo Estructural"** para detallar encapados y generar despieces.
   * Visita la pestaña **"Ubicación"** para generar mapas regionales georreferenciados.

---

## ⚙️ Uso de Comandos Masivos (PowerShell)

SINCAL utiliza **PowerShell 7** para procesar docenas de planos `.dwg` a la vez. No necesitas abrir AutoCAD.

1. Abre la carpeta de Windows donde están tus planos.
2. Haz clic en la barra de direcciones superior (donde sale la ruta).
3. Borra el texto, escribe `cmd` y presiona **Enter**.
4. En la ventana negra, escribe directamente el nombre de la herramienta (ej. `PURGEALL`, `PAGESETUP-A1`, `PUBLISH`) y presiona **Enter**.