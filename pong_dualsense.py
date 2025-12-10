import pygame
import sys
import pygame.gfxdraw

# ----------------- INICIALIZACIÓN -----------------
pygame.init()
pygame.joystick.init()
pygame.mixer.init()

# Detectar control
use_controller = pygame.joystick.get_count() > 0
if use_controller:
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print("Control PS5 detectado:", joystick.get_name())
else:
    print("No hay control PS5, funcionará con teclado (2P con flechas).")

# ----------------- LAYOUT GENERAL -----------------
GAME_W, GAME_H = 600, 600          # área de juego (cuadrado para Snake)
LEFT_PANEL_W = 280                 # panel de kernel / HID (reducido)
FOOTER_H = 200                     # espacio para el DualSense (reducido)
SCREEN_W = LEFT_PANEL_W + GAME_W
SCREEN_H = GAME_H + FOOTER_H

screen_flags = pygame.RESIZABLE
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), screen_flags)
# Superficie lógica donde dibujamos a tamaño base y luego la escalamos a la ventana
canvas = pygame.Surface((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Snake Final - Menú, Pausa, DualSense (UI mejorada)")

clock = pygame.time.Clock()

# ----------------- RECURSOS -----------------
hit_sound = pygame.mixer.Sound("pong_hit.wav")
point_sound = pygame.mixer.Sound("pong_point.wav")
menu_sound = pygame.mixer.Sound("menu_select.wav")

font = pygame.font.SysFont("Consolas", 22, bold=True)
big_font = pygame.font.SysFont("Consolas", 40, bold=True)
small_font = pygame.font.SysFont("Consolas", 16)

# Constantes del juego SNAKE
GRID_SIZE = 10
CELL_SIZE = GAME_W // GRID_SIZE  # pixels por celda
INITIAL_LIVES = 3

# HID labels
AXIS_LABELS = {
    0: "ABS_X  (Left Stick X)",
    1: "ABS_Y  (Left Stick Y)",
    2: "ABS_Z  (Right Stick X / L2)",
    3: "ABS_RZ (Right Stick Y / R2)"
}

BUTTON_LABELS = {
    0: "BTN_SOUTH (X)",
    1: "BTN_EAST  (Circle)",
    2: "BTN_WEST  (Square)",
    3: "BTN_NORTH (Triangle)",
    4: "Share", 5: "PS", 6: "Options", 7: "L3",
    8: "R3", 9: "L1", 10: "R1",
    # D-Pad como botones en tu mapeo
    11: "DPad Up", 12: "DPad Down", 13: "DPad Left", 14: "DPad Right",
    15: "Pad", 16: "MIC"
}

axis_states = {}
button_states = {}
event_log = []
MAX_LOG = 10

# Estado para evitar logs repetidos por ruido/rumble
last_axis_values = {}
hat_states = {}
input_mute_until = 0  # ms

# Umbrales para registrar cambios en ejes
AXIS_LOG_THRESHOLD = 0.18  # sólo loguear cambios mayores a este delta
AXIS_DEADZONE = 0.28      # considerar muerto si dentro de este rango

# RAW signals buffer (kernel -> HID -> datos binarios)
raw_signals = []  # lista de bytes
RAW_MAX = 8

# Snapshot of internal memory to display in panel
kernel_memory = {}

# Glow de botones
button_glow = {}        # btn_id -> timestamp
GLOW_DURATION = 350     # ms

# Colores para glow
BUTTON_COLORS = {
    0: (70, 180, 255),   # X
    1: (255, 90, 150),   # O
    2: (180, 120, 255),  # Square
    3: (120, 255, 170),  # Triangle
    4: (80, 220, 255),   # L1
    5: (80, 220, 255),   # R1
    6: (140, 140, 255),  # L2
    7: (140, 140, 255),  # R2
}

# ----------------- UTILIDADES HID -----------------
def log_event(text):
    event_log.append(text)
    if len(event_log) > MAX_LOG:
        event_log.pop(0)

def handle_joystick_events(event):
    """Actualiza logs y estados HID."""
    global axis_states, button_states, last_axis_values, hat_states, input_mute_until
    if not use_controller:
        return
    now = pygame.time.get_ticks()

    # Si estamos en periodo de mute por vibración, ignorar logs de ejes/HAT
    muted = now < input_mute_until

    if event.type == pygame.JOYBUTTONDOWN:
        btn = event.button
        button_states[btn] = True
        button_glow[btn] = pygame.time.get_ticks()
        log_event(f"[BTN] {BUTTON_LABELS.get(btn, f'BTN_{btn}')}")
        # RAW: B <btn>
        try:
            raw = bytes([0x42, btn & 0xFF])
            raw_signals.append(raw)
            if len(raw_signals) > RAW_MAX:
                raw_signals.pop(0)
        except Exception:
            pass
    elif event.type == pygame.JOYBUTTONUP:
        btn = event.button
        button_states[btn] = False
        # No registrar botón al soltar para evitar duplicados en el log
    elif event.type == pygame.JOYAXISMOTION:
        axis = event.axis
        val = joystick.get_axis(axis)
        prev = last_axis_values.get(axis, 0.0)
        # Aplicar deadzone: valores pequeños son tratados como 0
        disp_val = 0.0 if abs(val) < AXIS_DEADZONE else val
        # Registrar sólo si cambio significativo
        if not muted and abs(disp_val - prev) > AXIS_LOG_THRESHOLD:
            axis_states[axis] = val
            last_axis_values[axis] = disp_val
            log_event(f"[AXIS] {AXIS_LABELS.get(axis, f'AXIS_{axis}')} = {val:.2f}")
            # RAW: A <axis> <value8>
            try:
                q = int(max(-127, min(127, val * 127)))
                raw = bytes([0x41, axis & 0xFF, q & 0xFF])
                raw_signals.append(raw)
                if len(raw_signals) > RAW_MAX:
                    raw_signals.pop(0)
            except Exception:
                pass
        else:
            # Actualizar estado interno sin log si no supera umbral
            axis_states[axis] = val
            last_axis_values[axis] = disp_val
    elif event.type == pygame.JOYHATMOTION:
        # Juega with HAT: sólo loguear si cambia respecto estado previo
        hat_idx = 0
        prev_hat = hat_states.get(hat_idx, (0, 0))
        if not muted and event.value != prev_hat:
            hat_states[hat_idx] = event.value
            log_event(f"[HAT] {event.value}")
            # RAW: H <x> <y>
            try:
                hx, hy = event.value
                raw = bytes([0x48, (hx & 0xFF), (hy & 0xFF)])
                raw_signals.append(raw)
                if len(raw_signals) > RAW_MAX:
                    raw_signals.pop(0)
            except Exception:
                pass
        else:
            hat_states[hat_idx] = event.value


def trigger_rumble(joy, duration_ms=200, strong=0.7, weak=0.3):
    """Intentar activar vibración/rumble de manera segura.
    - joy: pygame.joystick.Joystick instance
    """
    global input_mute_until
    try:
        # pygame 2.1+ tiene Joystick.rumble
        if hasattr(joy, 'rumble'):
            joy.rumble(strong, weak, int(duration_ms))
            # Silenciar logs de ejes/HAT durante la vibración (+ pequeño buffer)
            input_mute_until = pygame.time.get_ticks() + int(duration_ms) + 120
            return True
    except Exception:
        pass

    try:
        # Intentar usar pygame.haptic (si está disponible y vinculado)
        if hasattr(pygame, 'haptic'):
            h = pygame.haptic.Haptic(joy)
            h.rumble_play(int(duration_ms), int(strong * 0x7fff))
            input_mute_until = pygame.time.get_ticks() + int(duration_ms) + 120
            return True
    except Exception:
        pass

    return False

def axis_up_down(axis_val, threshold=0.5):
    """Devuelve -1, 0 o 1 según movimiento vertical con deadzone."""
    if axis_val < -threshold:
        return -1
    if axis_val > threshold:
        return 1
    return 0


def present_frame():
    """Escala el canvas a la ventana actual y presenta en pantalla."""
    window_w, window_h = screen.get_size()
    scale = min(window_w / SCREEN_W, window_h / SCREEN_H)
    target_w = int(SCREEN_W * scale)
    target_h = int(SCREEN_H * scale)

    # Letterbox: fondo limpio y centrado
    screen.fill((0, 0, 0))
    scaled = pygame.transform.smoothscale(canvas, (target_w, target_h))
    offset_x = (window_w - target_w) // 2
    offset_y = (window_h - target_h) // 2
    screen.blit(scaled, (offset_x, offset_y))
    pygame.display.flip()

# ----------------- DIBUJO DEL DUALSENSE (SVG STYLE) -----------------
def draw_dualsense(surface, center_x, center_y, max_w, max_h, axes, btns):
    """
    Dibuja un DualSense estilo SVG minimalista (como GamepadTester),
    escalado para caber dentro de max_w x max_h.

    - axes: dict {axis_index: value_float (-1..1)}
    - btns: dict {button_index: bool}
    """

    # --- Config base del SVG original ---
    SVG_W, SVG_H = 441.0, 383.0   # viewBox del SVG que compartiste

    # Escala para que quepa en el espacio disponible
    scale = min(max_w / SVG_W, max_h / SVG_H)
    if scale <= 0:
        return

    stroke_color = (195, 210, 240)       # hsl(210,50%,85%) ~ azul clarito
    stroke_width = max(1, int(3 * scale))
    outline_alpha = 255

    # Helper para transformar coords SVG → pantalla
    def T(x, y):
        # centro del svg
        sx = (x - SVG_W / 2.0) * scale + center_x
        sy = (y - SVG_H / 2.0) * scale + center_y
        return int(sx), int(sy)

    # ---------- DIBUJO: Silueta (aprox paths LOutline & ROutline) ----------
    left_outline_pts = [
        (220.5, 294.5),
        (195.0, 294.5),
        (150.0, 294.5),
        (81.5, 378.5),
        (49.5, 378.5),
        (17.5, 378.5),
        (4.0, 317.5),
        (4.0, 271.1),
        (43.5, 165.5),
        (55.0, 137.5),
        (66.5, 109.5),
        (95.5, 92.0),
        (128.0, 92.0),
        (154.0, 92.0),
        (200.5, 92.0),
        (220.5, 92.0),
    ]
    right_outline_pts = [
        (220.0, 294.5),
        (245.5, 294.5),
        (290.5, 294.5),
        (335.5, 294.5),
        (359.0, 378.5),
        (391.0, 378.5),
        (423.0, 378.5),
        (436.5, 317.5),
        (436.5, 271.1),
        (397.0, 165.5),
        (385.5, 137.5),
        (374.0, 109.5),
        (345.0, 92.0),
        (312.5, 92.0),
        (286.5, 92.0),
        (240.0, 92.0),
        (220.0, 92.0),
    ]

    import pygame.gfxdraw

    # Dibujar silhouette suavizada
    def draw_polyline(points):
        if len(points) < 2:
            return
        transformed = [T(x, y) for (x, y) in points]
        pygame.draw.aalines(surface, stroke_color, False, transformed, True)

    draw_polyline(left_outline_pts)
    draw_polyline(right_outline_pts)

    # ---------- CÍRCULOS PRINCIPALES (sticks, D-pad, botones frontales) ----------
    circles = {
        "LStickOutline": (113, 160, 37.5),
        "RStickOutline": (278, 238, 37.5),
        "DOutline":      (166, 238, 37.5),
        "BOutline":      (329, 160, 37.5),
    }

    for _, (cx, cy, r) in circles.items():
        cx_s, cy_s = T(cx, cy)
        r_s = int(r * scale)
        pygame.gfxdraw.aacircle(surface, cx_s, cy_s, r_s, stroke_color)
        pygame.gfxdraw.aacircle(surface, cx_s, cy_s, r_s - 1, stroke_color)

    # ---------- L1 / R1 rectángulos ----------
    l1 = (111.5, 61.5, 41, 13)
    r1 = (289.5, 61.5, 41, 13)
    for (x, y, w, h) in (l1, r1):
        x1, y1 = T(x, y)
        x2, y2 = T(x + w, y + h)
        rect = pygame.Rect(x1, y1, x2 - x1, y2 - y1)
        pygame.draw.rect(surface, stroke_color, rect, max(1, int(2 * scale)), border_radius=int(6 * scale))

    # ---------- L2 / R2 (aprox) ----------
    def draw_capsule(cx, cy, w, h):
        cx_s, cy_s = T(cx, cy)
        w_s = int(w * scale)
        h_s = int(h * scale)
        rect = pygame.Rect(cx_s - w_s//2, cy_s - h_s//2, w_s, h_s)
        pygame.draw.ellipse(surface, stroke_color, rect, max(1, int(2 * scale)))

    draw_capsule(138.5, 23, 30, 40)  # L2
    draw_capsule(303.5, 23, 30, 40)  # R2

    # ---------- L-stick y R-stick puntos móviles ----------
    ls_center = (113, 160)
    rs_center = (278, 238)

    lx = axes.get(0, 0.0)
    ly = axes.get(1, 0.0)
    rx = axes.get(2, 0.0)
    ry = axes.get(3, 0.0)

    def draw_stick(center, ax_x, ax_y):
        cx, cy = center
        cx_s, cy_s = T(cx, cy)
        max_r = 20 * scale
        x_off = int(ax_x * max_r)
        y_off = int(ax_y * max_r)
        dot_r = int(7 * scale)

        pygame.gfxdraw.filled_circle(surface, cx_s + x_off, cy_s + y_off, dot_r, (230, 236, 248))
        pygame.gfxdraw.aacircle(surface, cx_s + x_off, cy_s + y_off, dot_r, (120, 140, 180))

    draw_stick(ls_center, lx, ly)
    draw_stick(rs_center, rx, ry)

    # ---------- D-Pad (flechas) ----------
    d_cx, d_cy, d_r = circles["DOutline"]
    base_len = d_r * 0.6

    def draw_dpad_arrow(direction, pressed=False):
        bx, by = d_cx, d_cy
        if direction == "up":
            points = [
                (bx, by - base_len),
                (bx - base_len * 0.6, by - base_len * 0.1),
                (bx + base_len * 0.6, by - base_len * 0.1),
            ]
        elif direction == "down":
            points = [
                (bx, by + base_len),
                (bx - base_len * 0.6, by + base_len * 0.1),
                (bx + base_len * 0.6, by + base_len * 0.1),
            ]
        elif direction == "left":
            points = [
                (bx - base_len, by),
                (bx - base_len * 0.1, by - base_len * 0.6),
                (bx - base_len * 0.1, by + base_len * 0.6),
            ]
        else:  # right
            points = [
                (bx + base_len, by),
                (bx + base_len * 0.1, by - base_len * 0.6),
                (bx + base_len * 0.1, by + base_len * 0.6),
            ]

        pts_t = [T(x, y) for (x, y) in points]
        col = (stroke_color[0], stroke_color[1], stroke_color[2])
        if pressed:
            fill = (220, 230, 255)
            pygame.gfxdraw.filled_polygon(surface, pts_t, fill)
        pygame.gfxdraw.aapolygon(surface, pts_t, col)

    draw_dpad_arrow("up")
    draw_dpad_arrow("down")
    draw_dpad_arrow("left")
    draw_dpad_arrow("right")

    # ---------- Botones ABXY (círculo "BOutline") ----------
    bx_cx, bx_cy, bx_r = circles["BOutline"]
    offsets = {
        "top":    (0, -bx_r * 0.55),
        "right":  (bx_r * 0.55, 0),
        "bottom": (0, bx_r * 0.55),
        "left":   (-bx_r * 0.55, 0),
    }

    mapping = [
        (3, "top",    (120, 255, 170)),   # Triangle – verde
        (1, "right",  (255, 90, 150)),    # O – rosa/rojo
        (0, "bottom", (70, 180, 255)),    # X – azul
        (2, "left",   (205, 205, 240)),   # Square – gris claro
    ]

    for btn_index, pos_key, base_col in mapping:
        ox, oy = offsets[pos_key]
        px, py = T(bx_cx + ox, bx_cy + oy)
        r_btn = int(9 * scale)
        pressed = btns.get(btn_index, False)

        fill_col = (base_col if pressed else (10, 10, 10))
        pygame.gfxdraw.filled_circle(surface, px, py, r_btn, fill_col)
        pygame.gfxdraw.aacircle(surface, px, py, r_btn, base_col)

        if not pressed:
            pygame.gfxdraw.filled_circle(surface, px - int(3*scale), py - int(3*scale), int(3*scale), (230, 240, 255))

    # ---------- Meta buttons (LMeta, RMeta) ----------
    meta_L = (185, 162)
    meta_R = (259, 162)
    for (mx, my) in (meta_L, meta_R):
        mx_s, my_s = T(mx, my)
        r_m = int(10 * scale)
        pygame.gfxdraw.aacircle(surface, mx_s, my_s, r_m, stroke_color)

    # ---------- Texto etiqueta ----------
    label = small_font.render("DualSense Wireless Controller (SVG style)", True, (200, 210, 235))
    surface.blit(label, (center_x - label.get_width() // 2, center_y + int((SVG_H/2 + 12) * scale)))

# ----------------- PANEL KERNEL / HID -----------------
def draw_kernel_panel(surface, pause_buttons):
    """Panel izquierdo compacto con eventos y ejes HID."""
    # Fondo
    panel_rect = pygame.Rect(0, 0, LEFT_PANEL_W, SCREEN_H)
    pygame.draw.rect(surface, (10, 10, 16), panel_rect)
    pygame.draw.rect(surface, (50, 70, 120), panel_rect, 2)

    # Header general
    header_rect = pygame.Rect(0, 0, LEFT_PANEL_W, 40)
    pygame.draw.rect(surface, (18, 18, 28), header_rect)
    title = small_font.render("HID / KERNEL MONITOR", True, (180, 200, 240))
    surface.blit(title, (8, 10))

    # Línea separadora
    pygame.draw.line(surface, (50, 70, 110), (0, 40), (LEFT_PANEL_W, 40), 2)

    # ---- Bloque: Event Log (más compacto) ----
    block1 = pygame.Rect(8, 50, LEFT_PANEL_W - 16, 140)
    pygame.draw.rect(surface, (18, 18, 28), block1, border_radius=6)
    pygame.draw.rect(surface, (40, 120, 180), block1, 1, border_radius=6)
    h1 = small_font.render("Eventos HID", True, (100, 180, 255))
    surface.blit(h1, (block1.x + 8, block1.y + 4))

    y = block1.y + 22
    for line in event_log[-5:]:
        bullet = small_font.render("•", True, (100, 255, 150))
        surface.blit(bullet, (block1.x + 8, y))
        t = small_font.render(line, True, (190, 190, 190))
        surface.blit(t, (block1.x + 18, y))
        y += 20

    # ---- Bloque: Axis States (más compacto) ----
    # Acortamos este bloque para que termine justo después del segundo 'Right'
    block2 = pygame.Rect(8, 200, LEFT_PANEL_W - 16, 110)
    pygame.draw.rect(surface, (18, 18, 28), block2, border_radius=6)
    pygame.draw.rect(surface, (200, 170, 60), block2, 1, border_radius=6)
    h2 = small_font.render("Joystick Izq.", True, (255, 200, 80))
    surface.blit(h2, (block2.x + 8, block2.y + 4))

    y = block2.y + 22
    # Solo mostrar L-stick y R2 (eje 2 y 3)
    for idx in [0, 1, 2, 3]:
        if idx in axis_states:
            label = AXIS_LABELS.get(idx, f"AXIS_{idx}").split("(")[1].strip(")")  # Solo la parte entre paréntesis
            val = axis_states[idx]
            bar_width = int(abs(val) * 30)
            color = (100, 200, 100) if val >= 0 else (255, 100, 100)
            t = small_font.render(f"{label[:6]}: {val:+.1f}", True, (200, 200, 200))
            surface.blit(t, (block2.x + 8, y))
            pygame.draw.rect(surface, color, (block2.x + 70, y + 2, bar_width, 12))
            y += 18

    # ---- Bloque: Señales RAW (Hex / Bin) ----
    block3 = pygame.Rect(8, block2.y + block2.height + 12, LEFT_PANEL_W - 16, 110)
    pygame.draw.rect(surface, (18, 18, 28), block3, border_radius=6)
    pygame.draw.rect(surface, (80, 160, 200), block3, 1, border_radius=6)
    h3 = small_font.render("Señales RAW (Hex / Bin)", True, (140, 220, 240))
    surface.blit(h3, (block3.x + 8, block3.y + 4))

    ry = block3.y + 22
    # Mostrar las últimas señales RAW (más recientes abajo)
    raw_to_show = raw_signals[-5:]
    for raw in raw_to_show:
        try:
            hex_str = ' '.join(f"{b:02X}" for b in raw)
            bin_str = ' '.join(f"{b:08b}" for b in raw)
            t1 = small_font.render(hex_str, True, (200, 200, 200))
            surface.blit(t1, (block3.x + 8, ry))
            ry += 16
            t2 = small_font.render(bin_str, True, (120, 180, 180))
            surface.blit(t2, (block3.x + 10, ry))
            ry += 14
        except Exception:
            continue

    # ---- Bloque: Estado Interno (Ciclo Von Neumann) ----
    block4 = pygame.Rect(8, block3.y + block3.height + 12, LEFT_PANEL_W - 16, 160)
    pygame.draw.rect(surface, (18, 18, 28), block4, border_radius=6)
    pygame.draw.rect(surface, (200, 160, 80), block4, 1, border_radius=6)
    h4 = small_font.render("Estado Interno (Ciclo Von Neumann)", True, (240, 200, 140))
    surface.blit(h4, (block4.x + 8, block4.y + 4))

    ry = block4.y + 22
    # Mostrar snapshot de kernel_memory
    km = kernel_memory
    lines = []
    try:
        lines.append(f"SCORE={km.get('score', '-')}")
        lines.append(f"VIDAS={km.get('lives', '-')}")
        lines.append(f"LEN={km.get('len_snake', '-')}")
        lines.append(f"DIR={km.get('direction', '-')}")
        lines.append(f"NEXT={km.get('next_direction', '-')}")
        lines.append(f"SPD={km.get('speed', '-')}")
        lines.append(f"FRAME={km.get('frame_count', '-')}")
        im = km.get('input_mute', 0)
        lines.append(f"MUTE(ms)={max(0, int(im))}")
        lines.append(f"RAW={km.get('raw_count', 0)}")
        lines.append(f"P={km.get('particles', 0)}")
    except Exception:
        lines = ["-"]

    for ln in lines[:8]:
        t = small_font.render(ln, True, (200, 200, 200))
        surface.blit(t, (block4.x + 8, ry))
        ry += 16

    # Info de pausa
    txt = ", ".join(f"B{b}" for b in pause_buttons) if pause_buttons else "-"
    bottom_label = small_font.render(f"Pausa: {txt}", True, (140, 140, 200))
    surface.blit(bottom_label, (8, SCREEN_H - 30))

# -----------------  MENÚ PRINCIPAL -----------------
def draw_menu(selected_index):
    canvas.fill((5, 5, 12))
    title = big_font.render("S N A K E", True, (255, 255, 255))
    canvas.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 80))

    options = ["Jugar", "Salir"]
    for i, text in enumerate(options):
        color = (255, 255, 0) if i == selected_index else (200, 200, 200)
        t = font.render(text, True, color)
        canvas.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 220 + i * 60))

    info = small_font.render(
        "Mover: ↑/↓/←/→ o D-Pad/L-Stick  |  Seleccionar: Enter / X",
        True, (150, 150, 150)
    )
    canvas.blit(info, (SCREEN_W // 2 - info.get_width() // 2, SCREEN_H - 60))

def menu_loop():
    selected = 0
    last_move = 0
    cooldown = 200  # ms

    while True:
        draw_menu(selected)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            # Teclado
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % 2
                    menu_sound.play()
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % 2
                    menu_sound.play()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    menu_sound.play()
                    return selected

            # Control
            if use_controller:
                handle_joystick_events(event)
                # Selección con X
                if event.type == pygame.JOYBUTTONDOWN and event.button == 0:  # X
                    menu_sound.play()
                    return selected
                # D-pad mapeado como botones (11 arriba, 12 abajo)
                if event.type == pygame.JOYBUTTONDOWN and event.button in (11, 12):
                    now = pygame.time.get_ticks()
                    if event.button == 11 and now - last_move > cooldown:
                        selected = (selected - 1) % 2
                        last_move = now
                        menu_sound.play()
                    if event.button == 12 and now - last_move > cooldown:
                        selected = (selected + 1) % 2
                        last_move = now
                        menu_sound.play()
                if event.type == pygame.JOYHATMOTION:
                    hat_x, hat_y = event.value
                    now = pygame.time.get_ticks()
                    if hat_y == 1 and now - last_move > cooldown:
                        selected = (selected - 1) % 2
                        last_move = now
                        menu_sound.play()
                    if hat_y == -1 and now - last_move > cooldown:
                        selected = (selected + 1) % 2
                        last_move = now
                        menu_sound.play()

        # Movimiento con stick
        if use_controller:
            axis_val = joystick.get_axis(1)
            direction = axis_up_down(axis_val, 0.6)
            now = pygame.time.get_ticks()
            if direction != 0 and now - last_move > cooldown:
                selected = (selected + direction) % 2
                last_move = now
                menu_sound.play()

        present_frame()
        present_frame()
        clock.tick(60)

# ----------------- MENÚ DE PAUSA -----------------
def pause_menu():
    selected = 0
    last_move = 0
    cooldown = 200

    # Limpiar log de eventos al entrar en pausa
    event_log.clear()

    # Pantalla completa (toda la ventana lógica)
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    while True:
        # Dibujar fondo transparente sobre *toda* la ventana
        overlay.fill((0, 0, 0, 180))
        canvas.blit(overlay, (0, 0))

        # Título centrado
        title = big_font.render("PAUSADO", True, (255, 255, 255))
        canvas.blit(title, (
            SCREEN_W // 2 - title.get_width() // 2,
            SCREEN_H // 2 - 150
        ))

        # Opciones
        options = ["Reanudar", "Salir al menú"]
        for i, txt in enumerate(options):
            color = (255, 255, 0) if i == selected else (220, 220, 220)
            t = font.render(txt, True, color)
            canvas.blit(
                t,
                (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H // 2 - 40 + i * 50)
            )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            # Teclado
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % 2
                    menu_sound.play()
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % 2
                    menu_sound.play()
                elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_p):
                    menu_sound.play()
                    return "resume" if selected == 0 else "menu"

            # Control PS5
            if use_controller:
                handle_joystick_events(event)

                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:  # X
                        menu_sound.play()
                        return "resume" if selected == 0 else "menu"

                # D-pad mapeado a botones (11 arriba, 12 abajo)
                if event.type == pygame.JOYBUTTONDOWN and event.button in (11, 12):
                    now = pygame.time.get_ticks()
                    if event.button == 11 and now - last_move > cooldown:
                        selected = (selected - 1) % 2
                        last_move = now
                        menu_sound.play()
                    if event.button == 12 and now - last_move > cooldown:
                        selected = (selected + 1) % 2
                        last_move = now
                        menu_sound.play()

                # Stick vertical
                if event.type == pygame.JOYAXISMOTION:
                    axis = joystick.get_axis(1)
                    if axis < -0.6 and pygame.time.get_ticks() - last_move > cooldown:
                        selected = (selected - 1) % 2
                        last_move = pygame.time.get_ticks()
                        menu_sound.play()
                    if axis > 0.6 and pygame.time.get_ticks() - last_move > cooldown:
                        selected = (selected + 1) % 2
                        last_move = pygame.time.get_ticks()
                        menu_sound.play()

                # D-pad (hat)
                if event.type == pygame.JOYHATMOTION:
                    hat_x, hat_y = event.value
                    now = pygame.time.get_ticks()
                    if hat_y == 1 and now - last_move > cooldown:
                        selected = (selected - 1) % 2
                        last_move = now
                        menu_sound.play()
                    if hat_y == -1 and now - last_move > cooldown:
                        selected = (selected + 1) % 2
                        last_move = now
                        menu_sound.play()

        present_frame()
        clock.tick(60)

# ----------------- LOOP DE JUEGO -----------------
def game_loop(mode):

    # AUTO-DETECTAR BOTÓN OPTIONS
    pause_buttons = []
    for btn_id, name in BUTTON_LABELS.items():
        if "Options" in name or "OPTION" in name or "PS" in name:
            pause_buttons.append(btn_id)

# fallback
    if 9 not in pause_buttons:
        pause_buttons.append(9)

    """
    Juego de Snake en un mapa de 10x10
    """
    global axis_states, button_states
    # Limpiar log de eventos al iniciar la partida
    event_log.clear()

    # Estados HID
    if use_controller:
        axis_states = {i: 0.0 for i in range(joystick.get_numaxes())}
        button_states = {i: False for i in range(joystick.get_numbuttons())}
        # inicializar valores previos para debounce
        last_axis_values = {i: 0.0 for i in range(joystick.get_numaxes())}
        # Inicializar hat_states (asumir un hat index 0 si existe)
        hat_states = {0: (0, 0)} if joystick.get_numhats() > 0 else {}
        pause_buttons = [9, 10, 16]  # distintos drivers mapean Options aquí
    else:
        axis_states = {}
        button_states = {}
        pause_buttons = []

    # Vidas
    lives = INITIAL_LIVES

    # Inicializar Snake
    snake = [(5, 5), (4, 5), (3, 5)]  # Lista de segmentos (cabeza primero)
    direction = (1, 0)  # Dirección (dx, dy)
    next_direction = (1, 0)
    food = (7, 7)
    score = 0
    game_over_flag = False
    
    # Velocidad del juego (frames entre movimientos)
    speed = 10
    frame_count = 0
    # Partículas al comer (inicializadas más abajo cuando conocemos origen de juego)
    particles = []  # cada partícula: dict{x,y,vx,vy,life,maxlife,clr,size}
    
    # Controles
    last_move_time = pygame.time.get_ticks()
    move_cooldown = 100  # ms para evitar múltiples movimientos rápidos

    game_origin_x = LEFT_PANEL_W
    game_origin_y = 0

    # Posiciones usadas para dibujar suavemente (pixeles)
    draw_positions = [
        (game_origin_x + x * CELL_SIZE + 2, game_origin_y + y * CELL_SIZE + 2)
        for (x, y) in snake
    ]

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if use_controller:
                handle_joystick_events(event)
                if event.type == pygame.JOYBUTTONDOWN and event.button in pause_buttons:
                    menu_sound.play()
                    result = pause_menu()
                    if result == "menu":
                        return

                # Controles con D-pad (HAT)
                if event.type == pygame.JOYHATMOTION:
                    hat_x, hat_y = event.value
                    now = pygame.time.get_ticks()
                    if now - last_move_time > move_cooldown:
                        if hat_y == 1 and direction != (0, 1):  # Arriba
                            next_direction = (0, -1)
                            last_move_time = now
                        elif hat_y == -1 and direction != (0, -1):  # Abajo
                            next_direction = (0, 1)
                            last_move_time = now
                        elif hat_x == -1 and direction != (1, 0):  # Izquierda
                            next_direction = (-1, 0)
                            last_move_time = now
                        elif hat_x == 1 and direction != (-1, 0):  # Derecha
                            next_direction = (1, 0)
                            last_move_time = now

                # Controles con botones (D-pad mapeado 11..14, face buttons 0..3, L1/R1)
                if event.type == pygame.JOYBUTTONDOWN:
                    btn = event.button
                    now = pygame.time.get_ticks()
                    # Movimientos D-pad mapeados como botones
                    if now - last_move_time > move_cooldown:
                        if btn == 11 and direction != (0, 1):  # DPad Arriba
                            next_direction = (0, -1)
                            last_move_time = now
                        elif btn == 12 and direction != (0, -1):  # DPad Abajo
                            next_direction = (0, 1)
                            last_move_time = now
                        elif btn == 13 and direction != (1, 0):  # DPad Izquierda
                            next_direction = (-1, 0)
                            last_move_time = now
                        elif btn == 14 and direction != (-1, 0):  # DPad Derecha
                            next_direction = (1, 0)
                            last_move_time = now

                    # Face buttons como movimiento (Triangle=3 Up, Circle=1 Right, X=0 Down, Square=2 Left)
                    if now - last_move_time > move_cooldown:
                        if btn == 3 and direction != (0, 1):
                            next_direction = (0, -1)
                            last_move_time = now
                        elif btn == 1 and direction != (-1, 0):
                            next_direction = (1, 0)
                            last_move_time = now
                        elif btn == 0 and direction != (0, -1):
                            next_direction = (0, 1)
                            last_move_time = now
                        elif btn == 2 and direction != (1, 0):
                            next_direction = (-1, 0)
                            last_move_time = now

                    # L1 / R1 para ajustar velocidad
                    if btn == 9:  # L1
                        speed = max(2, speed - 1)
                        log_event(f"Speed: {speed}")
                    elif btn == 10:  # R1
                        speed = min(30, speed + 1)
                        log_event(f"Speed: {speed}")

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_p, pygame.K_ESCAPE):
                    menu_sound.play()
                    result = pause_menu()
                    if result == "menu":
                        return
                # Controles de teclado
                if event.key == pygame.K_UP and direction != (0, 1):
                    next_direction = (0, -1)
                elif event.key == pygame.K_DOWN and direction != (0, -1):
                    next_direction = (0, 1)
                elif event.key == pygame.K_LEFT and direction != (1, 0):
                    next_direction = (-1, 0)
                elif event.key == pygame.K_RIGHT and direction != (-1, 0):
                    next_direction = (1, 0)

        # Controles con joystick izquierdo
        if use_controller:
            now = pygame.time.get_ticks()
            lx = axis_states.get(0, 0.0)
            ly = axis_states.get(1, 0.0)
            
            # Determinar dirección según stick izquierdo
            if now - last_move_time > move_cooldown:
                if abs(lx) > abs(ly):  # Movimiento horizontal dominante
                    if lx < -0.5 and direction != (1, 0):
                        next_direction = (-1, 0)
                        last_move_time = now
                    elif lx > 0.5 and direction != (-1, 0):
                        next_direction = (1, 0)
                        last_move_time = now
                else:  # Movimiento vertical dominante
                    if ly < -0.5 and direction != (0, 1):
                        next_direction = (0, -1)
                        last_move_time = now
                    elif ly > 0.5 and direction != (0, -1):
                        next_direction = (0, 1)
                        last_move_time = now

            # También aceptar stick derecho (axes 2/3) como alternativa
            rx = axis_states.get(2, 0.0)
            ry = axis_states.get(3, 0.0)
            if now - last_move_time > move_cooldown:
                if abs(rx) > abs(ry):
                    if rx < -0.5 and direction != (1, 0):
                        next_direction = (-1, 0)
                        last_move_time = now
                    elif rx > 0.5 and direction != (-1, 0):
                        next_direction = (1, 0)
                        last_move_time = now
                else:
                    if ry < -0.5 and direction != (0, 1):
                        next_direction = (0, -1)
                        last_move_time = now
                    elif ry > 0.5 and direction != (0, -1):
                        next_direction = (0, 1)
                        last_move_time = now

        # Actualizar dirección si no hace un giro de 180°
        direction = next_direction

        # Mover serpiente
        frame_count += 1
        if frame_count >= speed:
            frame_count = 0
            
            # Calcular nueva cabeza
            head_x, head_y = snake[0]
            dx, dy = direction
            new_head = (head_x + dx, new_head_y := head_y + dy)
            
            # Comprobar colisiones con bordes o consigo misma => perder vida
            died = False
            if new_head[0] < 0 or new_head[0] >= GRID_SIZE or new_head[1] < 0 or new_head[1] >= GRID_SIZE:
                died = True
            if new_head in snake:
                died = True

            if died:
                # Restar vida y reiniciar si quedan vidas
                lives -= 1
                log_event(f"Vida perdida! Quedan: {lives}")
                point_sound.play()
                try:
                    if use_controller:
                        trigger_rumble(joystick, duration_ms=350, strong=1.0, weak=0.6)
                except Exception:
                    pass
                pygame.time.wait(600)
                # Si no quedan vidas, game over y volver al menú
                if lives <= 0:
                    # Limpiar log y volver al menú
                    event_log.clear()
                    pygame.time.wait(300)
                    return
                # Si quedan vidas, reiniciar serpiente y estado
                snake = [(5, 5), (4, 5), (3, 5)]
                direction = (1, 0)
                next_direction = (1, 0)
                # Regenerar comida fuera de la serpiente
                import random
                while True:
                    food = (random.randint(0, GRID_SIZE - 1), random.randint(0, GRID_SIZE - 1))
                    if food not in snake:
                        break
                # Reset draw positions and particles
                draw_positions = [
                    (game_origin_x + x * CELL_SIZE + 2, game_origin_y + y * CELL_SIZE + 2)
                    for (x, y) in snake
                ]
                particles = []
                # Continuar al siguiente frame sin crecer
                continue
            
            # Agregar cabeza
            snake.insert(0, new_head)
            
            # Comprobar si comió comida
            if new_head == food:
                score += 10
                hit_sound.play()
                # Vibrar control si está disponible
                try:
                    if use_controller:
                        trigger_rumble(joystick, duration_ms=220, strong=0.9, weak=0.4)
                except Exception:
                    pass
                # Generar partículas al comer
                import random
                cx = game_origin_x + new_head[0] * CELL_SIZE + CELL_SIZE / 2
                cy = game_origin_y + new_head[1] * CELL_SIZE + CELL_SIZE / 2
                for _ in range(12):
                    particles.append({
                        'x': cx,
                        'y': cy,
                        'vx': random.uniform(-2.5, 2.5),
                        'vy': random.uniform(-2.5, 2.5),
                        'life': random.randint(18, 36),
                        'maxlife': 36,
                        'clr': (255, 170, 60),
                        'size': random.randint(2, 5)
                    })
                # Generar nueva comida en posición aleatoria
                while True:
                    food = (random.randint(0, GRID_SIZE - 1), random.randint(0, GRID_SIZE - 1))
                    if food not in snake:
                        break
            else:
                # Si no comió, quitar último segmento
                snake.pop()

        # ----------------- DIBUJAR -----------------
        # Actualizar snapshot del kernel (estado interno) para panel
        try:
            kernel_memory['score'] = score
            kernel_memory['lives'] = lives
            kernel_memory['len_snake'] = len(snake)
            kernel_memory['direction'] = direction
            kernel_memory['next_direction'] = next_direction
            kernel_memory['speed'] = speed
            kernel_memory['frame_count'] = frame_count
            kernel_memory['input_mute'] = input_mute_until - pygame.time.get_ticks()
            kernel_memory['raw_count'] = len(raw_signals)
            kernel_memory['particles'] = len(particles)
            kernel_memory['draw_positions'] = len(draw_positions)
            # Snapshot of axis short form
            kernel_memory['axes'] = {k: round(v, 2) for k, v in axis_states.items()} if axis_states else {}
            kernel_memory['buttons_pressed'] = [b for b, v in button_states.items() if v]
        except Exception:
            pass
        # Fondo general
        canvas.fill((8, 8, 14))

        # Panel kernel/HID
        draw_kernel_panel(canvas, pause_buttons)

        # Área de juego: tablero tipo ajedrez con dos tonos de verde
        light_green = (40, 160, 60)
        dark_green = (20, 110, 35)
        cell_margin = 0
        for gx in range(GRID_SIZE):
            for gy in range(GRID_SIZE):
                col = light_green if ((gx + gy) % 2 == 0) else dark_green
                rx = game_origin_x + gx * CELL_SIZE + cell_margin
                ry = game_origin_y + gy * CELL_SIZE + cell_margin
                rw = CELL_SIZE - cell_margin * 2
                rh = CELL_SIZE - cell_margin * 2
                pygame.draw.rect(canvas, col, (rx, ry, rw, rh))
        # Borde del área de juego
        pygame.draw.rect(canvas, (10, 40, 20), (game_origin_x, game_origin_y, GAME_W, GAME_H), 4, border_radius=6)

        # Dibujar comida (efecto pulsante)
        food_x, food_y = food
        food_rect = pygame.Rect(
            game_origin_x + food_x * CELL_SIZE + 2,
            game_origin_y + food_y * CELL_SIZE + 2,
            CELL_SIZE - 4, CELL_SIZE - 4
        )
        pulse = abs(pygame.time.get_ticks() % 600 - 300) / 300.0
        food_color = (
            int(255 * (0.6 + 0.4 * pulse)),
            int(100 * (0.6 + 0.4 * pulse)),
            int(80 * (0.6 + 0.4 * pulse))
        )
        pygame.draw.ellipse(canvas, food_color, food_rect)
        pygame.draw.ellipse(canvas, (255, 150, 100), food_rect, 2)
        center_x = food_rect.centerx
        center_y = food_rect.centery
        pygame.gfxdraw.filled_circle(canvas, int(center_x), int(center_y - CELL_SIZE // 8), 3, (255, 200, 150))

        # Actualizar posiciones dibujadas (suavizado) y dibujar serpiente
        smoothing = 0.32
        # Ajustar draw_positions si la longitud cambió
        if len(draw_positions) < len(snake):
            if draw_positions:
                draw_positions.insert(0, draw_positions[0])
            else:
                draw_positions.insert(0, (game_origin_x + snake[0][0] * CELL_SIZE + 2, game_origin_y + snake[0][1] * CELL_SIZE + 2))
        while len(draw_positions) > len(snake):
            draw_positions.pop()

        tail_index = len(snake) - 1
        for i, (sx, sy) in enumerate(snake):
            target_x = game_origin_x + sx * CELL_SIZE + 2
            target_y = game_origin_y + sy * CELL_SIZE + 2
            cur_x, cur_y = draw_positions[i]
            nx = cur_x + (target_x - cur_x) * smoothing
            ny = cur_y + (target_y - cur_y) * smoothing
            draw_positions[i] = (nx, ny)

            seg_rect = pygame.Rect(int(nx), int(ny), CELL_SIZE - 4, CELL_SIZE - 4)
            # Cabeza
            if i == 0:
                # Outer border (dark blue)
                pygame.draw.rect(canvas, (6, 18, 60), seg_rect.inflate(4, 4), border_radius=8)
                # Main head gradient (top -> bottom, light blue to deep blue)
                head_grad = pygame.Surface((seg_rect.width, seg_rect.height))
                top_col = (180, 220, 255)
                bot_col = (30, 80, 200)
                for yy in range(seg_rect.height):
                    t = yy / max(1, seg_rect.height - 1)
                    r = int(top_col[0] * (1 - t) + bot_col[0] * t)
                    g = int(top_col[1] * (1 - t) + bot_col[1] * t)
                    b = int(top_col[2] * (1 - t) + bot_col[2] * t)
                    pygame.draw.line(head_grad, (r, g, b), (0, yy), (seg_rect.width, yy))
                canvas.blit(head_grad, (seg_rect.x, seg_rect.y))
                pygame.draw.rect(canvas, (220, 240, 255), seg_rect, 2, border_radius=8)
                # Ojos (oscuro)
                eye_x = seg_rect.x + seg_rect.width // 3
                eye_y = seg_rect.y + seg_rect.height // 3
                pygame.gfxdraw.filled_circle(canvas, int(eye_x), int(eye_y), 3, (8, 12, 18))
                pygame.gfxdraw.filled_circle(canvas, int(eye_x + seg_rect.width // 3), int(eye_y), 3, (8, 12, 18))
                # Brillo superior (sutil)
                shine = pygame.Surface((seg_rect.width, max(2, seg_rect.height // 3)), pygame.SRCALPHA)
                pygame.draw.ellipse(shine, (255, 255, 255, 36), (0, 0, seg_rect.width, seg_rect.height // 2))
                canvas.blit(shine, (seg_rect.x, seg_rect.y - seg_rect.height // 6))
            # Cola
            elif i == tail_index:
                tail_color = (10, 30, 120)
                pygame.draw.rect(canvas, tail_color, seg_rect, border_radius=4)
                pygame.draw.rect(canvas, (40, 80, 160), seg_rect, 1, border_radius=4)
                # Small tip circle indicating tail end (darker blue)
                try:
                    if len(snake) >= 2:
                        tx, ty = snake[-1]
                        px, py = snake[-2]
                        dx_t = tx - px
                        dy_t = ty - py
                        tip_x = seg_rect.centerx + dx_t * (CELL_SIZE // 4)
                        tip_y = seg_rect.centery + dy_t * (CELL_SIZE // 4)
                        pygame.gfxdraw.filled_circle(canvas, int(tip_x), int(tip_y), 3, (5, 10, 40))
                except Exception:
                    pass
            else:
                depth = int(180 - min(100, i * 5))
                body_color = (30, 80, max(80, depth))
                pygame.draw.rect(canvas, body_color, seg_rect, border_radius=4)
                pygame.draw.rect(canvas, (90, 140, 220), seg_rect, 1, border_radius=4)

        # Dibujar partículas y actualizar
        new_particles = []
        for p in particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vx'] *= 0.96
            p['vy'] *= 0.96
            p['life'] -= 1
            alpha = int(255 * (p['life'] / p['maxlife']))
            if alpha > 0:
                surf = pygame.Surface((p['size'] * 2, p['size'] * 2), pygame.SRCALPHA)
                pygame.gfxdraw.filled_circle(surf, p['size'], p['size'], p['size'], (*p['clr'], alpha))
                canvas.blit(surf, (int(p['x'] - p['size']), int(p['y'] - p['size'])))
                new_particles.append(p)
        particles = new_particles

        # Score y vidas (estilo retro verde)
        score_text = font.render(f"SCORE: {score} | LONGITUD: {len(snake)}", True, (160, 255, 140))
        canvas.blit(score_text, (
            game_origin_x + GAME_W // 2 - score_text.get_width() // 2,
            8
        ))

        # Dibujar vidas como corazones pixel-art en la esquina superior izquierda del área de juego
        heart_base_x = game_origin_x + 8
        heart_base_y = 8
        heart_gap = 6
        # Corazones en rojo
        heart_color = (220, 20, 60)
        dark_color = (110, 20, 30)
        for i in range(lives):
            hx = heart_base_x + i * (CELL_SIZE // 2 + heart_gap)
            hy = heart_base_y
            # Dibujar corazón simple: dos círculos y un triángulo/rect
            # círculos
            pygame.gfxdraw.filled_circle(canvas, hx + 3, hy + 3, 3, heart_color)
            pygame.gfxdraw.filled_circle(canvas, hx + 8, hy + 3, 3, heart_color)
            # parte inferior
            pts = [(hx + 1, hy + 5), (hx + 10, hy + 5), (hx + 5, hy + 11)]
            pygame.draw.polygon(canvas, heart_color, pts)
            pygame.draw.polygon(canvas, dark_color, pts, 1)

        # Footer para DualSense
        footer_rect = pygame.Rect(0, GAME_H, SCREEN_W, FOOTER_H)
        pygame.draw.rect(canvas, (8, 8, 12), footer_rect)
        pygame.draw.line(canvas, (40, 40, 60), (0, GAME_H), (SCREEN_W, GAME_H), 2)

        # DualSense centrado en el footer
        ctrl_cx = SCREEN_W // 2
        ctrl_cy = GAME_H + FOOTER_H // 2 + 5
        draw_dualsense(
            canvas, ctrl_cx, ctrl_cy,
            max_w=SCREEN_W - 200,    # reduce ancho útil del SVG
            max_h=(FOOTER_H - 60),   # reduce altura útil del SVG
            axes=axis_states,
            btns=button_states
        )

        present_frame()
        clock.tick(60)

# -----------------  MAIN -----------------
if __name__ == "__main__":
    while True:
        opt = menu_loop()   # 0 = Jugar, 1 = Salir
        if opt == 0:
            game_loop(0)
        else:
            pygame.quit()
            sys.exit()
