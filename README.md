# 🏛️ SINCAL - Instalador y Gestor de Estándares CAD

**SINCAL** es una aplicación de escritorio ligera, autónoma y conectada a la nube. Su objetivo principal es automatizar la distribución y configuración de los estándares de dibujo (AutoCAD y ZWCAD) para todo el equipo de trabajo, garantizando que todos utilicen las mismas rutinas, capas, bloques y plumillas.

---

## 🚀 Características Principales

* **Sincronización en la Nube:** Descarga automáticamente LISPs, scripts, formatos y configuraciones nuevas desde GitHub pulsando un solo botón.
* **Inyección Automática:** Se vincula silenciosamente a tu versión de AutoCAD o ZWCAD, cargando todos los comandos al iniciar el programa.
* **Instalación de Plumillas (CTB):** Copia los estilos de impresión corporativos directamente a las carpetas internas del software de CAD.
* **Procesamiento Masivo Nativo (PowerShell):** Permite procesar decenas de planos de golpe directamente desde la carpeta de Windows sin abrir AutoCAD.
* **Documentación (Wiki):** Una biblioteca interactiva dentro del .exe que explica cómo usar todos los comandos LISP y herramientas de procesamiento en lote.

---

## 💻 Guía de Uso Rápido

1. **Descarga el ejecutable:** Obten el archivo `SINCAL.exe`.
2. **Ejecuta como Administrador:** El programa solicitará permisos automáticamente para poder modificar los registros del sistema.
3. **Actualiza:** Ve a la pestaña "Sincronizador" y haz clic en **"Instalar / Actualizar Todo"**.
4. **Navega por la Wiki:** Usa el menú lateral de esta pestaña para descubrir qué hace cada comando y cómo te ahorrará horas de trabajo.

---

## ⚙️ Uso de Comandos Masivos (PowerShell)

Ahora SINCAL utiliza **PowerShell 7** para procesar docenas de planos `.dwg` a la vez. No necesitas abrir AutoCAD.

1. Abre la carpeta de Windows donde están tus planos.
2. Haz clic en la barra de direcciones superior (donde sale la ruta).
3. Borra el texto, escribe `cmd` y presiona **Enter**.
4. En la ventana negra, escribe directamente el nombre de la herramienta (ej. `PURGEALL`, `CUSTOM-PROPS`, `PUBLISH`) y presiona **Enter**.

*(El sistema detectará el comando puente y llamará a PowerShell de fondo de forma segura y transparente).*

---

## 🚀 Configuraciones de Inicio y Atajos (Startup)

El Estándar SINCAL incluye rutinas que se ejecutan automáticamente en segundo plano cada vez que abres un plano en AutoCAD o ZWCAD para prepararte el entorno de trabajo:

* **AutoCrearPropiedad (`AutoCrearPropiedad.lsp`):** Se ejecuta automáticamente al abrir un DWG. Su función es inyectar en la base de datos del archivo las propiedades personalizadas necesarias para las viñetas (Nombre_Estructura, Provincia, Comuna, Revisión, etc.). Si el plano es nuevo o le faltan estas propiedades, el script las crea con un valor por defecto. Si ya existen, las respeta. Esto prepara el terreno para que el actualizador masivo (`CUSTOM-PROPS`) funcione sin errores.

* **Activación de Entrada Dinámica (`AUTO-DYNMODE.lsp`):** Se ejecuta silenciosamente al arrancar y fuerza el encendido de la variable de sistema `DYNMODE` a valor 3. Esto garantiza que la "Entrada Dinámica" (las ventanas emergentes de medidas y comandos que siguen a tu cursor) esté siempre activa, estandarizando la experiencia de dibujo para todo el equipo.

* **Atajos Ultra Rápidos de Color (`MisColores.lsp`):** Este script te permite cambiar el color de cualquier objeto (o grupo de objetos) seleccionado de forma instantánea usando comandos de dos teclas. Está blindado mediante programación Visual LISP (ActiveX) para funcionar en cualquier idioma de CAD sin errores.
  
  **Comandos disponibles:**
  - Escribe **`C1`** + Enter: Cambia a Rojo
  - Escribe **`C2`** + Enter: Cambia a Amarillo
  - Escribe **`C3`** + Enter: Cambia a Verde
  - Escribe **`C4`** + Enter: Cambia a Cian
  - Escribe **`C5`** + Enter: Cambia a Azul
  - Escribe **`C6`** + Enter: Cambia a Magenta
  - Escribe **`C7`** + Enter: Cambia a Blanco/Negro
  - Escribe **`C8`** + Enter: Cambia a Gris
  - Escribe **`C9`** + Enter: Cambia a Gris Claro
  - Escribe **`C0`** + Enter: Restaura el color "Por Capa" (ByLayer)