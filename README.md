# 🏛️ SINCAL - Suite de Ingeniería y Estándares CAD

**SINCAL** es una potente aplicación de escritorio ligera, autónoma y conectada a la nube. Su objetivo es unificar los estándares de dibujo (AutoCAD/ZWCAD), automatizar tareas repetitivas de ingeniería estructural y procesar planos geográficos con alta precisión.

---

## 🚀 Características Principales

* **Sincronización en la Nube (OTA):** Descarga automáticamente LISPs, scripts, formatos, imágenes y configuraciones nuevas desde el repositorio corporativo.
* **Inyección Automática:** Se vincula silenciosamente a tu versión de AutoCAD/ZWCAD, cargando todos los comandos al iniciar el programa.
* **Procesamiento Masivo Nativo (PowerShell):** Permite procesar decenas de planos de golpe directamente desde la carpeta de Windows sin abrir AutoCAD.
* **Módulo Estructural (BIM 2D):** Generación inteligente de vistas de armaduras (Zapatas, Consolas, Muros), dibujo y despiece paramétrico, inyección de cotas matemáticas, y lectura de parámetros desde archivos JSON de proyecto.
* **Generador de Croquis de Ubicación (GIS):** Lector nativo de archivos `.kmz` (Google Earth) que, a través de un motor de interpolación espacial y mapas MOP pre-calibrados, estampa la ubicación exacta del puente en un PNG listo para AutoCAD.
* **Comandos en Vivo (Conexión COM):** Ejecuta comandos de forma remota en AutoCAD directamente desde la interfaz del programa.
* **Renombrado Avanzado:** Herramienta de interfaz para buscar, reemplazar y actualizar revisiones de planos DWG de forma masiva en milisegundos.
* **Documentación (Wiki):** Biblioteca interactiva integrada con todos los comandos y manuales.

---

## 💻 Guía de Uso Rápido

1. **Descarga el ejecutable:** Obtén el archivo `SINCAL.exe`.
2. **Ejecuta como Administrador:** El programa solicitará permisos automáticamente para conectarse al motor de CAD y el registro del sistema.
3. **Actualiza:** Ve a la pestaña "Sincronizador" y haz clic en **"Instalar / Actualizar Todo"**.
4. **Módulos Activos:** * Visita la pestaña **"Módulo Estructural"** para detallar encapados y generar despieces.
   * Visita la pestaña **"Ubicación"** para generar mapas regionales georreferenciados.

---

## ⚙️ Uso de Comandos Masivos (PowerShell)

SINCAL utiliza **PowerShell 7** para procesar docenas de planos `.dwg` a la vez. No necesitas abrir AutoCAD.

1. Abre la carpeta de Windows donde están tus planos.
2. Haz clic en la barra de direcciones superior (donde sale la ruta).
3. Borra el texto, escribe `cmd` y presiona **Enter**.
4. En la ventana negra, escribe directamente el nombre de la herramienta (ej. `PURGEALL`, `PAGESETUP-A1`, `PUBLISH`) y presiona **Enter**.