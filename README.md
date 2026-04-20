# 🛠️ Herramientas de Automatización para CAD

Desarrollado por G. Mardones, dibujante proyectista Sincal Ltda.

Bienvenido al repositorio central de herramientas, scripts y rutinas LISP para AutoCAD y ZWCAD. 

Este repositorio actúa como el **servidor maestro** para el instalador y actualizador automático. A través de este sistema, los usuarios finales pueden mantener sus herramientas de diseño siempre actualizadas sin necesidad de descargar o configurar archivos manualmente.

---

## 📁 Estructura del Repositorio

El repositorio está organizado de la siguiente manera para que el actualizador de Python pueda leerlo correctamente:

* 📂 **/lisps/**: Contiene todas las rutinas `.lsp` (ej. dibujo automático, cálculos, etc.) para AutoCAD/ZWCAD.
* 📂 **/scripts/**: Contiene archivos `.bat` u otros scripts de soporte para la configuración del sistema.
* 📄 **version.json**: ¡El archivo más importante! Es el índice que la aplicación lee para saber si hay actualizaciones disponibles y qué archivos debe descargar el usuario.

---

## 🚀 ¿Cómo funciona el Actualizador Automático?

Existe una aplicación de escritorio (un `.exe` independiente) que los usuarios instalan en sus computadoras. Cada vez que esa aplicación se ejecuta en segundo plano:
1.  Lee el archivo `version.json` de este repositorio público.
2.  Compara la versión de la nube con la versión instalada en la PC del usuario.
3.  Si la versión en GitHub es mayor, descarga los archivos crudos (*Raw*) y reemplaza los antiguos en la PC local de forma silenciosa.

---

## 📝 Instrucciones de Actualización (Para el Administrador)

Si deseas agregar una nueva herramienta o actualizar una existente para que llegue a todos los usuarios, sigue estos 3 pasos:

### 1. Sube o reemplaza el archivo
Copia tu nuevo archivo `.lsp` o `.bat` dentro de la carpeta correspondiente (`/lisps/` o `/scripts/`).

### 2. Edita el archivo `version.json`
Abre el archivo `version.json` y realiza dos acciones clave:
* **Sube el número de versión:** Si estaba en `"1.0.0"`, cámbialo a `"1.0.1"`.
* **Verifica la lista de archivos:** Asegúrate de que la ruta exacta de tu archivo esté dentro de la lista `"archivos"`.

**Ejemplo de cómo debe verse:**
```json
{
    "version": "1.0.1",
    "archivos": [
        "lisps/dibujar_muros.lsp",
        "scripts/limpiar_capas.bat"
    ]
}
