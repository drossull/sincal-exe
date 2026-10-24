# Reglas del proyecto

Estas reglas se aplican a todo el repositorio.

- Limitar el trabajo a los cambios solicitados expresamente por el usuario.
- Los mensajes de corrección o redirección ajustan la tarea activa: conservar lo avanzado, incorporar la nueva dirección y continuar hasta completar el alcance acordado. No abandonar ni dar por terminada una tarea por recibir estos mensajes; sólo detenerla si el usuario lo pide o hay un impedimento concreto que se explique.
- No cambiar, sustituir ni rediseñar la interfaz si el usuario no lo pide.
- No reorganizar, mover, agrupar ni cambiar la dependencia entre módulos si el usuario no lo pide.
- Una solicitud de corrección, compilación, actualización o instalación no autoriza cambios adicionales de interfaz ni de organización de módulos.
- Si el cambio solicitado requiere alterar la interfaz o reorganizar módulos fuera del alcance autorizado, explicar la necesidad y obtener autorización explícita antes de hacerlo.

## Flujo acordado del generador de armaduras

- Cargar el JSON de Proyecto Puentes, calcular las armaduras y elegir el elemento, instancia y vista que se insertará.
- Enviar una orden por vista a AutoCAD/ZWCAD: dos esquinas opuestas (superior izquierda e inferior derecha) para referencias rectangulares; tres esquinas consecutivas (superior izquierda, superior derecha e inferior derecha) para la planta esviada E-E de la zapata. Reconstruir la cuarta esquina del paralelogramo y validar dimensiones y esviaje contra el cálculo/JSON antes de insertar. Los puntos NO son una ventana que capture líneas u objetos, ni autorizan deformar los fierros para encajarlos.
- Los nombres de las capas NO identifican los moldajes ni son un requisito de entrada. No pedir crear o renombrar capas para usar el generador.
- Trabajar sobre la selección explícita de la vista; no recorrer el dibujo completo ni consultar AutoCAD en segundo plano para identificar los elementos.
- Conservar la interfaz web y la organización de módulos; adaptar únicamente los controles necesarios para este flujo solicitado.
- Un botón por vista (frontal, A-A, etc.) debe iniciar una secuencia guiada de selección de los elementos correspondientes; los opcionales se incluyen según el JSON.
- Sólo las armaduras de zapata tienen reglas definidas actualmente. El usuario aún debe definir la naturaleza y distribución de los fierros de las demás estructuras; no inventar esas reglas ni presentar esos generadores como terminados.
