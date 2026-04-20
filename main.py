import os
import json
import requests

# --- CONFIGURACIÓN ---
# ¡IMPORTANTE! Cambia esto por tus datos reales de GitHub
USUARIO_GITHUB = "drossull" 
REPO_GITHUB = "sincal-exe"
RAMA = "main" 

URL_BASE_RAW = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPO_GITHUB}/{RAMA}/"
RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "MisHerramientasCAD") 

def generar_cargador_cad(lista_archivos):
    """Crea el archivo acaddoc.lsp que AutoCAD lee al iniciar"""
    ruta_cargador = os.path.join(RUTA_LOCAL_APP, "acaddoc.lsp")
    
    print("Generando archivo de auto-carga para CAD...")
    
    with open(ruta_cargador, 'w', encoding='utf-8') as f:
        f.write(';; --- CARGADOR AUTOMATICO DE HERRAMIENTAS ---\n')
        f.write('(princ "\\nVerificando y cargando herramientas personalizadas...")\n\n')
        
        for archivo in lista_archivos:
            if archivo.endswith('.lsp'):
                # Convertimos la ruta para que Lisp la entienda (con dobles barras \\)
                ruta_completa = os.path.join(RUTA_LOCAL_APP, archivo).replace('\\', '\\\\')
                # Escribimos el comando de carga segura en Lisp
                f.write(f'(if (findfile "{ruta_completa}") (load "{ruta_completa}"))\n')
                
        f.write('\n(princ "\\n¡Herramientas cargadas con éxito!")\n')
        f.write('(princ)\n')
        
    print(f"Cargador creado en: {ruta_cargador}")

def verificar_y_actualizar():
    print(f"Iniciando verificador de herramientas CAD...")
    os.makedirs(RUTA_LOCAL_APP, exist_ok=True)
    
    url_version_remota = URL_BASE_RAW + "version.json"
    try:
        respuesta_remota = requests.get(url_version_remota)
        respuesta_remota.raise_for_status()
        datos_remotos = respuesta_remota.json()
        version_nube = datos_remotos.get("version")
        archivos_a_descargar = datos_remotos.get("archivos", [])
    except Exception as e:
        print(f"Error al conectar con GitHub: {e}")
        return

    ruta_version_local = os.path.join(RUTA_LOCAL_APP, "version.json")
    version_local = "0.0.0" 
    
    if os.path.exists(ruta_version_local):
        with open(ruta_version_local, 'r') as f:
            version_local = json.load(f).get("version", "0.0.0")

    if version_nube > version_local:
        print(f"¡Actualizando! {version_local} -> {version_nube}")
        for archivo in archivos_a_descargar:
            url_archivo = URL_BASE_RAW + archivo
            ruta_guardado = os.path.join(RUTA_LOCAL_APP, archivo)
            os.makedirs(os.path.dirname(ruta_guardado), exist_ok=True)
            
            resp_archivo = requests.get(url_archivo)
            if resp_archivo.status_code == 200:
                with open(ruta_guardado, 'wb') as f:
                    f.write(resp_archivo.content)
        
        with open(ruta_version_local, 'w') as f:
            json.dump(datos_remotos, f, indent=4)
            
        # AQUÍ LLAMAMOS A LA NUEVA FUNCIÓN
        generar_cargador_cad(archivos_a_descargar)
        print("¡Actualización completada!")
    else:
        print("El sistema está en la última versión.")
        # También lo generamos por si el usuario lo borró por accidente
        generar_cargador_cad(archivos_a_descargar)

if __name__ == "__main__":
    verificar_y_actualizar()
