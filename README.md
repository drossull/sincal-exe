# 🏛️ SINCAL - Instalador y Gestor de Estándares CAD

**SINCAL** es una aplicación de escritorio ligera, autónoma y conectada a la nube, desarrollada en Python. Su objetivo principal es automatizar la distribución y configuración de los estándares de dibujo (AutoCAD y ZWCAD) para todo el equipo de trabajo, garantizando que todos los dibujantes utilicen las mismas rutinas, capas, bloques y plumillas sin configuraciones manuales complejas.

---

## 🚀 Características Principales

* **Sincronización en la Nube (OTA Updates):** No es necesario distribuir un nuevo `.exe` cada vez que hay un cambio. La aplicación compara su versión local con el archivo `version.json` del repositorio y descarga automáticamente los LISPs, scripts o formatos nuevos o modificados.
* **Inyección Automática en el Registro:** Detecta si el usuario tiene instalado AutoCAD o ZWCAD y vincula silenciosamente la ruta de los estándares al *Support File Search Path* del programa.
* **Instalación de Plumillas (CTB):** Localiza la ruta interna de *Plot Styles* del usuario y copia los estilos de impresión corporativos directamente en las entrañas del software.
* **Procesamiento Masivo (Batch):** Agrega la ruta de los scripts al `PATH` de Windows. Esto permite a los usuarios abrir una consola (CMD) en cualquier carpeta y procesar decenas de planos a la vez (ej. ejecutar limpiezas, auditar errores o publicar PDFs masivamente).
* **Instructivo Integrado:** Cuenta con una interfaz gráfica (GUI) con una pestaña de tutoriales interactivos que se alimentan del archivo `tutoriales.json` de la nube, documentando el uso de todos los comandos personalizados.

---

## 💻 Guía de Uso (Para el Usuario Final)

1. **Descarga el ejecutable:** Descarga el archivo `SINCAL.exe` proporcionado por el administrador.
2. **Ejecuta el programa:** Ábrelo (no requiere permisos de administrador).
3. **Actualiza:** Ve a la pestaña "Sincronizador" y haz clic en **"Instalar / Actualizar Todo"**.
4. **Aprende:** Ve a la pestaña "Instructivo" para leer qué hace cada comando y cómo utilizarlo.
5. **Abre tu CAD:** Al iniciar AutoCAD o ZWCAD, los comandos (ej. `SINCAL`, `BV`, `ZE`) ya estarán listos para usarse y las plumillas aparecerán en tu ventana de impresión.

### Uso de Comandos Masivos (Scripts)
Para procesar múltiples planos de golpe:

1. Ve a la carpeta de Windows donde tienes tus planos `.dwg`.
2. Haz clic en la barra de direcciones superior del Explorador de Archivos, escribe `cmd` y presiona **Enter**.
3. En la ventana negra, escribe el nombre del proceso (ej. `AUDIT`, `PUBLISH`, `PURGEALL`) y presiona **Enter**.

---

## 📂 Estructura del Repositorio

Para que el gestor funcione correctamente, el repositorio debe mantener esta estructura de carpetas:

```text
📁 sincal-exe
├── 📁 lisps/           # Rutinas AutoLISP (.lsp) de comandos personalizados (BV, DL2, ZE, etc.)
├── 📁 startup/         # Lisps de configuración de inicio (MisColores, AUTO-DYNMODE, etc.)
├── 📁 scripts/         # Archivos .bat y .scr para el procesamiento masivo de planos
├── 📁 plotstyles/      # Plumillas de impresión corporativas (.ctb)
├── 📁 masters/         # Archivo DWG maestro que contiene los bloques, estilos y capas base
├── 📄 version.json     # Archivo clave: Controla la versión actual y los archivos a descargar
├── 📄 tutoriales.json  # Base de datos de textos para la pestaña "Instructivo"
├── 📄 main.py          # Código fuente de la aplicación en Python
└── 🖼️ logo.ico         # Icono para la compilación del ejecutable