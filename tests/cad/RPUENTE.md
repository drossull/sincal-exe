# Pruebas nativas de RPUENTE

Ejecutar `rpuente_regression.scr` mediante SCRIPT o AcCoreConsole **en un DWG desechable**. Define la variable de entorno `SINCAL_TEST_ROOT` con la ruta absoluta del repositorio antes de iniciar CAD. El script crea geometría de prueba, modifica UCS y referencias a objetos, y termina la sesión sin guardar.

Se verifican 29 casos geométricos y uno interactivo: circunferencia por tres puntos, estabilidad con coordenadas UTM, proyección XY, puntos degenerados, sensibilidad de curvas tendidas, bulges positivos y negativos, arcos mayores, selección de segmentos con radios diferentes, vértices ambiguos, cierre, POLYLINE antigua, ARC/CIRCLE y conversión explícita de unidades. También se comprueba que medir no altere la entidad.

Resultado esperado: `RPUENTE_FAILURES=0` y `RPUENTE_FINAL_FAILURES=0`. Las pruebas no determinan el radio del puente de una captura: se necesita seleccionar su geometría real, con las unidades correctas.
