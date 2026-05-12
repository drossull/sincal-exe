# 🏛️ SINCAL - Instalador y Gestor de Estándares CAD

**SINCAL** es una aplicación de escritorio ligera, autónoma y conectada a la nube. Su objetivo principal es automatizar la distribución y configuración de los estándares de dibujo (AutoCAD y ZWCAD) para todo el equipo de trabajo, garantizando que todos utilicen las mismas rutinas, capas, bloques y plumillas.

---

## 🚀 Características Principales

* **Sincronización en la Nube (OTA):** Descarga automáticamente LISPs, scripts, formatos y configuraciones nuevas desde GitHub pulsando un solo botón.
* **Inyección Automática:** Se vincula silenciosamente a tu versión de AutoCAD o ZWCAD, cargando todos los comandos al iniciar el programa.
* **Instalación de Plumillas (CTB):** Copia los estilos de impresión corporativos directamente a las carpetas internas del software de CAD.
* **Procesamiento Masivo Nativo (PowerShell):** Permite procesar decenas de planos de golpe directamente desde la carpeta de Windows sin abrir AutoCAD.
* **Herramientas de Interfaz (NUEVO):** Incorpora un panel en vivo para secuestrar pestañas abiertas de CAD y una herramienta ultrarrápida de renombrado de revisiones.
* **Documentación (Wiki):** Una biblioteca interactiva dentro del `.exe` que explica cómo usar todos los comandos LISP y herramientas de procesamiento.

---

## 💻 Guía de Uso Rápido

1. **Descarga el ejecutable:** Obten el archivo `SINCAL.exe`.
2. **Ejecuta como Administrador:** El programa solicitará permisos automáticamente para poder modificar los registros del sistema.
3. **Actualiza:** Ve a la pestaña "Sincronizador" y haz clic en **"Instalar / Actualizar Todo"**.
4. **Navega por la Wiki:** Usa el menú lateral de la pestaña "Documentación" para descubrir qué hace cada comando y cómo te ahorrará horas de trabajo.

---

## ⚙️ Uso de Comandos Masivos (PowerShell)

SINCAL utiliza **PowerShell 7** para procesar docenas de planos `.dwg` a la vez. No necesitas abrir AutoCAD.

1. Abre la carpeta de Windows donde están tus planos.
2. Haz clic en la barra de direcciones superior (donde sale la ruta).
3. Borra el texto, escribe `cmd` y presiona **Enter**.
4. En la ventana negra, escribe directamente el nombre de la herramienta (ej. `PURGEALL`, `PAGESETUP-A1`, `PUBLISH`) y presiona **Enter**.

*(El sistema detectará el comando puente y llamará al motor de fondo de forma segura).*

---

## ⚡ Nuevas Herramientas Integradas

El programa ahora cuenta con dos herramientas que interactúan directamente desde su interfaz:

1. **Comandos en Vivo (Conexión COM):** Te permite escribir un comando (ej. `_.QSAVE` o `_.ZOOM _E`) en la caja de texto de SINCAL y enviarlo a todas las pestañas que tengas abiertas en tu AutoCAD/ZWCAD en ese momento. *(Nota: Requiere que abras tu programa de dibujo como Administrador para que se puedan comunicar).*
2. **Renombrado Masivo de Revisiones:** Si tienes una carpeta con 50 planos y necesitas subirles la revisión (ej. de la "C" a la "D"), usa el módulo de Renombrado. Escaneará la carpeta y cambiará la última letra de todos los nombres en un milisegundo sin tener que abrirlos.