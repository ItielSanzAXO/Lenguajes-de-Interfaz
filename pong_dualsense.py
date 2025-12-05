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
GAME_W, GAME_H = 880, 600          # área de juego
LEFT_PANEL_W = 380                 # panel de kernel / HID
FOOTER_H = 260                     # espacio para el DualSense
SCREEN_W = LEFT_PANEL_W + GAME_W
SCREEN_H = GAME_H + FOOTER_H

screen_flags = pygame.RESIZABLE
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), screen_flags)
# Superficie lógica donde dibujamos a tamaño base y luego la escalamos a la ventana
canvas = pygame.Surface((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Pong Final - Menú, Pausa, DualSense (UI mejorada)")

clock = pygame.time.Clock()

# ----------------- RECURSOS -----------------
hit_sound = pygame.mixer.Sound("pong_hit.wav")
point_sound = pygame.mixer.Sound("pong_point.wav")
menu_sound = pygame.mixer.Sound("menu_select.wav")

font = pygame.font.SysFont("Consolas", 22, bold=True)
big_font = pygame.font.SysFont("Consolas", 40, bold=True)
small_font = pygame.font.SysFont("Consolas", 16)

# Constantes del juego
PADDLE_W = 15
PADDLE_H = 90
BALL_SIZE = 14

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
    4: "L1", 5: "R1", 6: "L2", 7: "R2",
    8: "Share", 9: "Options",
    10: "L3", 11: "R3"
}

axis_states = {}
button_states = {}
event_log = []
MAX_LOG = 10

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
    global axis_states, button_states
    if not use_controller:
        return

    if event.type == pygame.JOYBUTTONDOWN:
        btn = event.button
        button_states[btn] = True
        button_glow[btn] = pygame.time.get_ticks()
        log_event(f"[BTN ↓] {BUTTON_LABELS.get(btn, f'BTN_{btn}')}")
    elif event.type == pygame.JOYBUTTONUP:
        btn = event.button
        button_states[btn] = False
        log_event(f"[BTN ↑] {BUTTON_LABELS.get(btn, f'BTN_{btn}')}")
    elif event.type == pygame.JOYAXISMOTION:
        axis = event.axis
        val = joystick.get_axis(axis)
        axis_states[axis] = val
        log_event(f"[AXIS] {AXIS_LABELS.get(axis, f'AXIS_{axis}')} = {val:.2f}")
    elif event.type == pygame.JOYHATMOTION:
        log_event(f"[HAT] {event.value}")

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
    """Panel izquierdo con diseño más bonito para eventos y ejes."""
    # Fondo
    panel_rect = pygame.Rect(0, 0, LEFT_PANEL_W, SCREEN_H)
    pygame.draw.rect(surface, (10, 10, 16), panel_rect)

    # Header general
    header_rect = pygame.Rect(0, 0, LEFT_PANEL_W, 50)
    pygame.draw.rect(surface, (18, 18, 26), header_rect)
    title = font.render("MONITOR HID / KERNEL", True, (220, 220, 255))
    surface.blit(title, (18, 12))

    # Línea separadora
    pygame.draw.line(surface, (70, 70, 90), (0, 50), (LEFT_PANEL_W, 50), 2)

    # ---- Bloque: Event Log ----
    block1 = pygame.Rect(16, 64, LEFT_PANEL_W - 32, 220)
    pygame.draw.rect(surface, (18, 18, 28), block1, border_radius=10)
    pygame.draw.rect(surface, (40, 120, 200), block1, 1, border_radius=10)
    h1 = small_font.render("Eventos HID (kernel → pygame)", True, (110, 190, 255))
    surface.blit(h1, (block1.x + 10, block1.y + 6))

    y = block1.y + 30
    for line in event_log[-7:]:
        bullet = small_font.render("•", True, (0, 255, 150))
        surface.blit(bullet, (block1.x + 12, y))
        t = small_font.render(line, True, (210, 210, 210))
        surface.blit(t, (block1.x + 24, y))
        y += 20

    # ---- Bloque: Axis States ----
    block2 = pygame.Rect(16, 300, LEFT_PANEL_W - 32, 220)
    pygame.draw.rect(surface, (18, 18, 28), block2, border_radius=10)
    pygame.draw.rect(surface, (220, 190, 70), block2, 1, border_radius=10)
    h2 = small_font.render("Ejes HID (estado actual)", True, (255, 220, 90))
    surface.blit(h2, (block2.x + 10, block2.y + 6))

    y = block2.y + 30
    for idx in sorted(axis_states.keys()):
        label = AXIS_LABELS.get(idx, f"AXIS_{idx}")
        val = axis_states[idx]
        t = small_font.render(f"{label}: {val:+.2f}", True, (230, 230, 230))
        surface.blit(t, (block2.x + 10, y))
        y += 20

    # Info de botón de pausa
    txt = ", ".join(f"B{b}" for b in pause_buttons) if pause_buttons else "-"
    bottom_label = small_font.render(f"Pausa: {txt} / Teclado: P o ESC", True, (160, 160, 220))
    surface.blit(bottom_label, (18, SCREEN_H - 30))

# ----------------- MENÚ PRINCIPAL -----------------
def draw_menu(selected_index):
    canvas.fill((5, 5, 12))
    title = big_font.render("P O N G", True, (255, 255, 255))
    canvas.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 80))

    options = ["1 Jugador (vs CPU)", "2 Jugadores", "Salir"]
    for i, text in enumerate(options):
        color = (255, 255, 0) if i == selected_index else (200, 200, 200)
        t = font.render(text, True, color)
        canvas.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 220 + i * 60))

    info = small_font.render(
        "Mover: ↑/↓ o D-Pad/Stick  |  Seleccionar: Enter / X",
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
                    selected = (selected - 1) % 3
                    menu_sound.play()
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % 3
                    menu_sound.play()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    menu_sound.play()
                    return selected

            # Control
            if use_controller:
                handle_joystick_events(event)
                if event.type == pygame.JOYBUTTONDOWN and event.button == 0:  # X
                    menu_sound.play()
                    return selected
                if event.type == pygame.JOYHATMOTION:
                    hat_x, hat_y = event.value
                    now = pygame.time.get_ticks()
                    if hat_y == 1 and now - last_move > cooldown:
                        selected = (selected - 1) % 3
                        last_move = now
                        menu_sound.play()
                    if hat_y == -1 and now - last_move > cooldown:
                        selected = (selected + 1) % 3
                        last_move = now
                        menu_sound.play()

        # Movimiento con stick
        if use_controller:
            axis_val = joystick.get_axis(1)
            direction = axis_up_down(axis_val, 0.6)
            now = pygame.time.get_ticks()
            if direction != 0 and now - last_move > cooldown:
                selected = (selected + direction) % 3
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
    mode = 0 -> 1 Jugador (vs CPU)
    mode = 1 -> 2 Jugadores
    """
    global axis_states, button_states

    # Estados HID
    if use_controller:
        axis_states = {i: 0.0 for i in range(joystick.get_numaxes())}
        button_states = {i: False for i in range(joystick.get_numbuttons())}
        pause_buttons = [9, 10, 16]  # distintos drivers mapean Options aquí
    else:
        axis_states = {}
        button_states = {}
        pause_buttons = []

    # Paletas y pelota
    p1_y = GAME_H // 2 - PADDLE_H // 2
    p2_y = GAME_H // 2 - PADDLE_H // 2
    ball_x = GAME_W // 2
    ball_y = GAME_H // 2
    ball_vx = 6
    ball_vy = 6
    score = 0
    cpu_speed = 6

    game_origin_x = LEFT_PANEL_W
    game_origin_y = 0

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

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_p, pygame.K_ESCAPE):
                    menu_sound.play()
                    result = pause_menu()
                    if result == "menu":
                        return

        keys = pygame.key.get_pressed()

        # Player 1
        if use_controller:
            ly = axis_states.get(1, 0.0)
            if abs(ly) > 0.15:
                p1_y += ly * 7
        else:
            if keys[pygame.K_w]:
                p1_y -= 7
            if keys[pygame.K_s]:
                p1_y += 7

        # Player 2
        if mode == 0:  # CPU
            if p2_y + PADDLE_H/2 < ball_y:
                p2_y += cpu_speed
            else:
                p2_y -= cpu_speed
        else:          # 2 jugadores (flechas)
            if keys[pygame.K_UP]:
                p2_y -= 7
            if keys[pygame.K_DOWN]:
                p2_y += 7

        p1_y = max(0, min(GAME_H - PADDLE_H, p1_y))
        p2_y = max(0, min(GAME_H - PADDLE_H, p2_y))

        # Movimiento pelota
        ball_x += ball_vx
        ball_y += ball_vy

        # Rebotes verticales
        if ball_y <= 0 or ball_y >= GAME_H - BALL_SIZE:
            ball_vy *= -1
            hit_sound.play()

        # Rebotes horizontal / puntos
        if ball_x <= 60 + PADDLE_W:
            if p1_y <= ball_y <= p1_y + PADDLE_H:
                ball_vx *= -1
                hit_sound.play()
                score += 1
            else:
                ball_x, ball_y = GAME_W // 2, GAME_H // 2
                ball_vx, ball_vy = 6, 6
                score = 0
                point_sound.play()

        if ball_x >= GAME_W - 60 - PADDLE_W - BALL_SIZE:
            if p2_y <= ball_y <= p2_y + PADDLE_H:
                ball_vx *= -1
                hit_sound.play()
            else:
                ball_x, ball_y = GAME_W // 2, GAME_H // 2
                ball_vx, ball_vy = -6, 6
                score = 0
                point_sound.play()

        # ----------------- DIBUJAR -----------------
        canvas.fill((12, 12, 18))

        # Panel kernel/HID
        draw_kernel_panel(canvas, pause_buttons)

        # Área de juego
        pygame.draw.rect(canvas, (0, 0, 0), (game_origin_x, game_origin_y, GAME_W, GAME_H))

        # Score
        score_text = font.render(f"SCORE: {score}", True, (255, 255, 255))
        canvas.blit(score_text, (
            game_origin_x + GAME_W // 2 - score_text.get_width() // 2,
            10
        ))

        # Paletas
        pygame.draw.rect(canvas, (255, 255, 255),
                         (game_origin_x + 60, game_origin_y + p1_y, PADDLE_W, PADDLE_H))
        pygame.draw.rect(canvas, (255, 255, 255),
                         (game_origin_x + GAME_W - 60 - PADDLE_W, game_origin_y + p2_y,
                          PADDLE_W, PADDLE_H))

        # Pelota
        pygame.draw.rect(canvas, (255, 255, 255),
                         (game_origin_x + ball_x, game_origin_y + ball_y, BALL_SIZE, BALL_SIZE))

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

# ----------------- MAIN -----------------
if __name__ == "__main__":
    while True:
        opt = menu_loop()   # 0 = 1P, 1 = 2P, 2 = salir
        if opt == 0:
            game_loop(0)
        elif opt == 1:
            game_loop(1)
        else:
            pygame.quit()
            sys.exit()
