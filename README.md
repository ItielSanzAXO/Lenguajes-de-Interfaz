Pong / Snake DualSense — Interfaz y diagnóstico

Este repositorio contiene una versión modificada del juego clásico (estilo Pong/Snake) con soporte y diagnósticos para gamepads (DualSense) usando `pygame`.

**Propósito:** servir como demo interactiva para experimentar entradas HID, gestionar el ruido de ejes (debounce), mostrar señales RAW y un "estado interno" por fotograma, además de una estética retro con tablero tipo ajedrez.

**Archivo principal:** `pong_dualsense.py`

**Estado:** código implementado y listo para ejecutar localmente con Python + pygame. Ver instrucciones de uso abajo.

**Requisitos**
- **Python 3.10+** (el entorno usado en el proyecto es Python 3.12 según el virtualenv incluido).
- **pygame** (se incluye en el entorno virtual `game_pong` dentro del repositorio). Instalar si hace falta:

```powershell
python -m pip install pygame
```

**Cómo ejecutar**
- Abrir PowerShell en la carpeta del proyecto (`C:\Users\itiel\Desktop\Lenguajes de Interfaz`).
- Ejecutar:

```powershell
python .\pong_dualsense.py
```

Si utilizas el virtualenv provisto (`game_pong`), activa la env antes de ejecutar:

```powershell
. .\game_pong\bin\Activate.ps1
python .\pong_dualsense.py
```

**Controles**
- Teclado:
  - **Flechas**: mover la serpiente (o paleta, según modo)
  - **Esc**: volver al menú / pausar
  - **Enter / Espacio**: seleccionar / reiniciar
- Gamepad (DualSense compatible):
  - Ejes analógicos: movimiento direccional (implementado con deadzone y debouncing)
  - Botones: acciones configuradas en `handle_joystick_events` (se registran en la UI de diagnóstico)

Paneles y diagnósticos integrados
- **Eventos HID**: ventana con eventos significativos del joystick (botones, ejes, hats) — se aplica deadzone y umbral de log para evitar spam.
- **Señales RAW (Hex / Bin)**: buffer corto que muestra paquetes RAW simplificados (formato pedagógico) de los eventos HID recientes.
- **Estado Interno (Ciclo Von Neumann)**: snapshot por fotograma con valores clave (`score`, `lives`, `len_snake`, `direction`, `speed`, `frame_count`, `input_mute` etc.) para depuración.

Características de juego
- **Sistema de vidas**: 3 vidas por defecto (`INITIAL_LIVES = 3`). Al perder una vida, la serpiente se reinicia y el tablero persiste hasta agotar vidas.
- **HUD retro**: corazones (vidas) y puntuación en pantalla.
- **Estética**: tablero tipo ajedrez verde y serpiente en paleta azul con cabeza/cola mejoradas.

Parámetros ajustables (variables en `pong_dualsense.py`)
- `AXIS_DEADZONE` (ej. 0.28): umbral mínimo para ignorar micro-ruidos de eje.
- `AXIS_LOG_THRESHOLD` (ej. 0.18): diferencia mínima para registrar un cambio de eje en el log.
- `RAW_MAX`: número de paquetes RAW mostrados en el panel.

Archivos y estructura importante
- `pong_dualsense.py` — juego y código principal.
- `game_pong/` — virtualenv local (incluye `pygame`).
- Sonidos esperados: `pong_hit.wav`, `pong_point.wav`, `menu_select.wav` (deben estar junto al script si se usan).

Depuración y solución de problemas
- Si ves que las entradas del joystick se repiten durante la vibración (rumble), el código ya incluye un periodo de "mute" (`input_mute_until`) mientras dura la vibración para evitar registros espurios.
- Si los ejes generan demasiado o muy poco logging, ajusta `AXIS_DEADZONE` y `AXIS_LOG_THRESHOLD` en el código.
- Para ver la salida de eventos en consola, ejecuta el script desde PowerShell; el panel izquierdo también muestra los eventos relevantes.

Contribuir
- Abrir un issue o enviar un pull request con mejoras (ajustes de sensibilidad, nuevo skin, exportar logs RAW, etc.).

Licencia
- Este repositorio no incluye una licencia explícita en el root; agrega una si necesitas un uso/redistribución concreto (por ejemplo, `MIT`).

Contacto
- Para dudas o ajustes rápidos, deja un issue en el repositorio o contáctame directamente desde tu flujo de trabajo.

Gracias por usar y probar este demo: juega, ajusta los thresholds y dime si quieres que añada controles para limpiar el buffer RAW o exportar los estados a archivo.
