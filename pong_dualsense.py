import pygame
import sys

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

# Pantalla
WIDTH, HEIGHT = 900, 600
# Panel sizes
LEFT_PANEL_W = 360
RIGHT_PANEL_W = 360
# Controller layout: 'right' or 'bottom'
CONTROLLER_LAYOUT = 'bottom'  # user requested bottom layout by default
# Height reserved for controller when placed at bottom
# Aumentado para dar más espacio vertical al mando y mejorar espaciado
CONTROLLER_H = 260
# Factor global de escala para el dibujo del controlador (ajústalo aquí)
CONTROLLER_SCALE = 5.25
# Screen size
# Si el layout es 'bottom' no agregamos la franja derecha al ancho total,
# así el área de juego + panel izquierdo ocupa todo el ancho y el footer
# inferior (control) puede usar el espacio completo.
if CONTROLLER_LAYOUT == 'right':
    SCREEN_W = LEFT_PANEL_W + WIDTH + RIGHT_PANEL_W
else:
    SCREEN_W = LEFT_PANEL_W + WIDTH
SCREEN_H = HEIGHT + (CONTROLLER_H if CONTROLLER_LAYOUT == 'bottom' else 0)
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Pong Final - Menú, Pausa, DualSense (layout)")

clock = pygame.time.Clock()

# Sonidos
hit_sound = pygame.mixer.Sound("pong_hit.wav")
point_sound = pygame.mixer.Sound("pong_point.wav")
menu_sound = pygame.mixer.Sound("menu_select.wav")

# Fuentes
font = pygame.font.SysFont("Consolas", 22, bold=True)
big_font = pygame.font.SysFont("Consolas", 40, bold=True)
small_font = pygame.font.SysFont("Consolas", 16)

# Constantes de juego
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
MAX_LOG = 8
# Glow system for button lighting (timestamps in ms)
button_glow = {}
GLOW_DURATION = 400  # ms

# Colors for buttons (used for glow and lightbar)
BUTTON_COLORS = {
    # Neon palette
    0: (70, 200, 255),   # X - cyan/blue neon
    1: (255, 80, 140),   # O - pink neon
    2: (180, 100, 255),  # Square - purple neon
    3: (80, 255, 160),   # Triangle - green neon
    4: (80,220,255),     # L1 - cyan soft
    5: (80,220,255),     # R1 - cyan soft
    6: (120,120,255),    # L2 - bluish
    7: (120,120,255),    # R2 - bluish
}

# ----------------- UTILIDADES -----------------
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
        # Registrar glow (timestamp)
        try:
            button_glow[btn] = pygame.time.get_ticks()
        except Exception:
            pass
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

# Deadzone
def axis_up_down(axis_val, threshold=0.5):
    """Devuelve -1, 0 o 1 según movimiento vertical con deadzone."""
    if axis_val < -threshold:
        return -1
    if axis_val > threshold:
        return 1
    return 0

# ----------------- DIBUJO DUALSENSE MINIMALISTA -----------------
def draw_dualsense_minimal(surface, center_x, center_y, axes, btns, max_width=None, max_height=None):
    # Dibujar en alta resolución y luego hacer downscale (supersampling) para antialias
    # Decide width target: use provided max_width (for bottom layout) or right panel width
    if max_width is None:
        max_width = RIGHT_PANEL_W
    # initial cap by width: reducir padding y permitir un ancho máximo mayor
    # (menos margen lateral y más capacidad para ampliar el mando)
    base_w = min(max(160, max_width - 20), 620)
    # if a max_height is provided, ensure the final height won't exceed it
    if max_height is not None:
        # final_h scales with aspect ratio 320x140
        estimated_h = int(base_w * 140 / 320)
        # si supera la altura disponible, ajustar ancho para que quepa
        if estimated_h > max_height:
            base_w = int(max_height * 320 / 140)
    # Aplicar factor de escala global y limitar a márgenes
    final_w = int(base_w * CONTROLLER_SCALE)
    # Asegurar que no sobrepase el ancho disponible
    final_w = min(final_w, max_width - 12, 720)
    final_w = max(final_w, 140)
    final_h = int(final_w * 140 / 320)
    w_hr = final_w * 2
    h_hr = final_h * 2
    temp = pygame.Surface((w_hr, h_hr), pygame.SRCALPHA)

    ox = w_hr // 2
    oy = h_hr // 2
    # Body rect en coordenadas locales
    body_rect = pygame.Rect(ox - 150, oy - 45, 300, 110)

    # Sombra: dibujar múltiples elipses translúcidas para simular blur
    for i in range(6, 0, -1):
        alpha = int(18 * i)
        srect = body_rect.inflate(i*6, i*3)
        pygame.draw.ellipse(temp, (0,0,0,alpha), (srect.x, srect.y+8, srect.w, srect.h))

    # Cuerpo con capas para degradado sutil
    layers = [ (250,250,250), (240,240,244), (230,230,236) ]
    for i, col in enumerate(layers):
        br = body_rect.inflate(-i*6, -i*4)
        pygame.draw.ellipse(temp, col, br)
    # Rim oscuro
    pygame.draw.ellipse(temp, (30,30,30), body_rect, 3)

    # Lightbar: rect con glow
    # Lightbar: rect con glow (color dinámico según botones)
    lb = pygame.Rect(ox - 40, oy - 54, 80, 8)
    now = pygame.time.get_ticks()
    # combinar colores de botones con glow
    combined = [0.0, 0.0, 0.0]
    any_glow = False
    for b, col in BUTTON_COLORS.items():
        ts = button_glow.get(b)
        if ts is None:
            continue
        dt = now - ts
        if dt < GLOW_DURATION:
            intensity = max(0.0, 1.0 - (dt / GLOW_DURATION))
            any_glow = True
            combined[0] += col[0] * intensity
            combined[1] += col[1] * intensity
            combined[2] += col[2] * intensity
    if any_glow:
        # normalizar para evitar overflow
        maxc = max(combined)
        if maxc > 255:
            factor = 255.0 / maxc
            combined = [c * factor for c in combined]
        glow_color = (int(combined[0]), int(combined[1]), int(combined[2]))
    else:
        glow_color = (90,160,255)

    # dibujar glow con el color calculado (más intenso para neón)
    for g in range(8,0,-1):
        alpha = 28 + g * 10
        gr = lb.inflate(g*8, g*3)
        pygame.draw.rect(temp, (glow_color[0], glow_color[1], glow_color[2], min(alpha,255)), gr, border_radius=8)
    pygame.draw.rect(temp, glow_color, lb, border_radius=6)

    # Agarres laterales (más definidos)
    left_grip = pygame.Rect(ox - 190, oy - 6, 90, 96)
    right_grip = pygame.Rect(ox + 100, oy - 6, 90, 96)
    pygame.draw.ellipse(temp, (220,220,225), left_grip)
    pygame.draw.ellipse(temp, (220,220,225), right_grip)
    pygame.draw.ellipse(temp, (40,40,40), left_grip, 2)
    pygame.draw.ellipse(temp, (40,40,40), right_grip, 2)
    pygame.draw.ellipse(temp, (200,200,205), left_grip.inflate(-18,-18))
    pygame.draw.ellipse(temp, (200,200,205), right_grip.inflate(-18,-18))

    # Touchpad con reflejo
    pad = pygame.Rect(ox - 70, oy - 32, 140, 48)
    pygame.draw.rect(temp, (36,36,40), pad, border_radius=12)
    inner = pad.inflate(-6,-8)
    pygame.draw.rect(temp, (58,58,62), inner, border_radius=10)
    # brillo superior del touchpad
    shine = pygame.Rect(inner.left+2, inner.top+2, inner.w-4, inner.h//2)
    pygame.draw.rect(temp, (255,255,255,28), shine, border_radius=8)

    # Sticks: bases con sombra y concavidad
    lsx = axes.get(0, 0.0)
    lsy = axes.get(1, 0.0)
    rsx = axes.get(2, 0.0)
    rsy = axes.get(3, 0.0)

    ls_center = (ox - 70, oy + 15)
    rs_center = (ox + 70, oy + 20)
    for c in [ls_center, rs_center]:
        pygame.draw.circle(temp, (18,18,18), c, 24)
        pygame.draw.circle(temp, (70,70,76), c, 20)
        pygame.draw.circle(temp, (38,38,44), (c[0]-4, c[1]-4), 10)

    lpos = (int(ls_center[0] + lsx * 10), int(ls_center[1] + lsy * 10))
    rpos = (int(rs_center[0] + rsx * 10), int(rs_center[1] + rsy * 10))
    pygame.draw.circle(temp, (200,200,200), lpos, 9)
    pygame.draw.circle(temp, (0,0,0), lpos, 9, 2)
    pygame.draw.circle(temp, (200,200,200), rpos, 9)
    pygame.draw.circle(temp, (0,0,0), rpos, 9, 2)

    # Botones frontales: base, color, brillo, símbolo
    face_buttons = {
        0: ("X", (ox + 115, oy + 28), (70, 120, 255)),
        1: ("O", (ox + 140, oy + 5), (255, 90, 90)),
        2: ("□", (ox + 90, oy + 5), (200, 200, 230)),
        3: ("△", (ox + 115, oy - 18), (100, 220, 120)),
    }
    for idx, (symbol, (bx, by), color) in face_buttons.items():
        pressed = btns.get(idx, False)
        # glow intensity based on timestamp
        ts = button_glow.get(idx)
        intensity = 0.0
        if ts is not None:
            dt = now - ts
            if dt < GLOW_DURATION:
                intensity = max(0.0, 1.0 - (dt / GLOW_DURATION))

        # dibujar halo (varias circunferencias alpha decrecientes) - estilo neón
        if intensity > 0:
            for r, a_mul in ((22, 220), (36, 140), (54, 48)):
                alpha = int(a_mul * intensity / 255 * 255)
                halo_col = (base_col[0], base_col[1], base_col[2], max(8, min(alpha,255)))
                pygame.draw.circle(temp, halo_col, (bx, by), r)

        offset = 2 if pressed else 0
        # sombra base
        pygame.draw.circle(temp, (8,8,8), (bx, by+offset+2), 16)
        # botón principal
        col = tuple(max(0, c - 18) for c in color) if pressed else color
        pygame.draw.circle(temp, col, (bx, by+offset), 14)
        # pequeño brillo
        pygame.draw.circle(temp, (255,255,255,30), (bx-4, by-6+offset), 6)
        t = small_font.render(symbol, True, (255,255,255))
        temp.blit(t, (bx - t.get_width()//2, by+offset - t.get_height()//2))

    # L1 / R1 y gatillos (neón)
    l1_rect = pygame.Rect(ox - 132, oy - 56, 60, 14)
    r1_rect = pygame.Rect(ox + 72, oy - 56, 60, 14)
    pygame.draw.rect(temp, (28,28,32), l1_rect, border_radius=6)
    pygame.draw.rect(temp, (28,28,32), r1_rect, border_radius=6)
    # glow para L1/R1 si hubo pulsación (neón)
    for bid, rect in ((4, l1_rect), (5, r1_rect)):
        tsb = button_glow.get(bid)
        if tsb is not None:
            dtb = now - tsb
            if dtb < GLOW_DURATION:
                inten = max(0.0, 1.0 - (dtb / GLOW_DURATION))
                col = BUTTON_COLORS.get(bid, (100,200,255))
                for mul, alpha_base in ((1.2,180),(2.6,88),(4.0,26)):
                    alpha = int(alpha_base * inten)
                    rrect = rect.inflate(int(10*mul), int(6*mul))
                    pygame.draw.rect(temp, (col[0], col[1], col[2], max(6, alpha)), rrect, border_radius=10)
    if btns.get(4, False):
        pygame.draw.rect(temp, (120,180,220), l1_rect.inflate(-6,-4), border_radius=5)
    if btns.get(5, False):
        pygame.draw.rect(temp, (120,180,220), r1_rect.inflate(-6,-4), border_radius=5)

    l2 = pygame.Rect(ox - 150, oy - 24, 40, 28)
    r2 = pygame.Rect(ox + 110, oy - 24, 40, 28)
    pygame.draw.ellipse(temp, (38,38,42), l2)
    pygame.draw.ellipse(temp, (38,38,42), r2)
    # glow para gatillos L2/R2 (neón)
    for bid, erot in ((6, l2), (7, r2)):
        tsb = button_glow.get(bid)
        if tsb is not None:
            dtb = now - tsb
            if dtb < GLOW_DURATION:
                inten = max(0.0, 1.0 - (dtb / GLOW_DURATION))
                col = BUTTON_COLORS.get(bid, (120,120,255))
                for r_mul, a_mul in ((1.0,160),(1.9,74),(3.2,22)):
                    alpha = int(a_mul * inten)
                    er = erot.inflate(int(6*r_mul), int(6*r_mul))
                    pygame.draw.ellipse(temp, (col[0],col[1],col[2], max(6,alpha)), er)
    if btns.get(6, False):
        pygame.draw.ellipse(temp, (160,160,210), l2.inflate(-6,-6))
    if btns.get(7, False):
        pygame.draw.ellipse(temp, (160,160,210), r2.inflate(-6,-6))

    # Brillo general: un pequeño reflejo en el cuerpo
    refl = pygame.Rect(ox - 110, oy - 42, 160, 38)
    pygame.draw.ellipse(temp, (255,255,255,18), refl)

    # Etiqueta más discreta
    label = small_font.render("DualSense — mejorado", True, (40,40,40))
    temp.blit(label, (ox - label.get_width() // 2, oy + 58))

    # Downscale con suavizado y blit en la superficie principal
    scaled = pygame.transform.smoothscale(temp, (final_w, final_h))
    sx = center_x - final_w // 2
    sy = center_y - final_h // 2
    surface.blit(scaled, (sx, sy))


# ----------------- MENÚ PRINCIPAL -----------------
def draw_menu(selected_index):
    screen.fill((5, 5, 10))

    # Centrar en toda la ventana (izq+centro+der)
    title = big_font.render("P O N G", True, (255, 255, 255))
    screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 80))

    options = ["1 Jugador (vs CPU)", "2 Jugadores", "Salir"]
    for i, text in enumerate(options):
        color = (255, 255, 0) if i == selected_index else (200, 200, 200)
        t = font.render(text, True, color)
        screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 200 + i * 60))

    info = small_font.render("Mover: ↑/↓ o Stick | Seleccionar: Enter o X", True, (150, 150, 150))
    screen.blit(info, (SCREEN_W // 2 - info.get_width() // 2, SCREEN_H - 40))

    pygame.display.flip()

def menu_loop():
    selected = 0
    last_move = 0
    cooldown = 200  # ms

    while True:
        draw_menu(selected)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            # ------------------- TECLADO -------------------
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % 3
                    menu_sound.play()
                if event.key == pygame.K_DOWN:
                    selected = (selected + 1) % 3
                    menu_sound.play()
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    menu_sound.play()
                    return selected

            # ------------------- CONTROL: BOTONES -------------------
            if use_controller:
                handle_joystick_events(event)

                # Botón X
                if event.type == pygame.JOYBUTTONDOWN and event.button == 0:
                    menu_sound.play()
                    return selected

                # ------------------- CONTROL: FLECHAS (HAT) -------------------
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

        # ------------------- CONTROL: STICK IZQUIERDO -------------------
        if use_controller:
            axis_val = joystick.get_axis(1)
            direction = 0
            if axis_val < -0.5:
                direction = -1
            elif axis_val > 0.5:
                direction = 1

            now = pygame.time.get_ticks()
            if direction != 0 and now - last_move > cooldown:
                selected = (selected + direction) % 3
                last_move = now
                menu_sound.play()

        clock.tick(60)

# ----------------- MENÚ DE PAUSA -----------------
def pause_menu():
    selected = 0
    last_axis_move_time = 0
    axis_cooldown = 200

    while True:
        # Dibujar overlay que cubre TODA la ventana (incluye panel derecho)
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        title = big_font.render("PAUSADO", True, (255, 255, 255))
        screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 140))

        options = ["Reanudar", "Salir al menú"]
        for i, txt in enumerate(options):
            color = (255, 255, 0) if i == selected else (220, 220, 220)
            t = font.render(txt, True, color)
            screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 220 + i * 50))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % 2
                    menu_sound.play()
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % 2
                    menu_sound.play()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_p, pygame.K_ESCAPE):
                    menu_sound.play()
                    if selected == 0:
                        return "resume"
                    else:
                        return "menu"

            if use_controller:
                handle_joystick_events(event)
                if event.type == pygame.JOYHATMOTION:
                    hat_x, hat_y = event.value
                    now = pygame.time.get_ticks()

                    if hat_y == 1 and now - last_axis_move_time > axis_cooldown:
                        selected = (selected - 1) % 2
                        last_axis_move_time = now
                        menu_sound.play()

                    if hat_y == -1 and now - last_axis_move_time > axis_cooldown:
                        selected = (selected + 1) % 2
                        last_axis_move_time = now
                        menu_sound.play()

                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:  # X
                        menu_sound.play()
                        return "resume" if selected == 0 else "menu"
                    if event.button == 9 or event.button == 16:  # Options o B16 también reanuda
                        menu_sound.play()
                        return "resume"

        # Stick para moverse
        if use_controller:
            axis_val = joystick.get_axis(1)
            dir_y = axis_up_down(axis_val, 0.5)
            now = pygame.time.get_ticks()
            if dir_y != 0 and now - last_axis_move_time > axis_cooldown:
                selected = (selected + dir_y) % 2
                last_axis_move_time = now
                menu_sound.play()

        clock.tick(60)

# ----------------- LOOP DE JUEGO -----------------
def game_loop(mode):
    """
    mode = 0 -> 1 Jugador (vs CPU)
    mode = 1 -> 2 Jugadores
    """
    global axis_states, button_states

    # Estados HID
    if use_controller:
        axis_states = {i: 0.0 for i in range(joystick.get_numaxes())}
        button_states = {i: False for i in range(joystick.get_numbuttons())}
        # Identificar botones de pausa cuando hay control
        # B16 es el botón de pausa indicado por el usuario; 9 se mantiene como fallback (Options)
        pause_buttons = [16, 9]
    else:
        axis_states = {}
        button_states = {}
        # Identificar qué botón es OPTIONS revisando nombres
        pause_buttons = []
        for btn_id, name in BUTTON_LABELS.items():
            if "Options" in name or "OPTIONS" in name:
                pause_buttons.append(btn_id)

        # En caso de que el driver lo mapee distinto
        if 9 not in pause_buttons:
            pause_buttons.append(9)


    # Paletas y pelota
    p1_y = HEIGHT // 2 - PADDLE_H // 2
    p2_y = HEIGHT // 2 - PADDLE_H // 2
    ball_x = WIDTH // 2
    ball_y = HEIGHT // 2
    ball_vx = 6
    ball_vy = 6
    score = 0
    cpu_speed = 6

    paused = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if use_controller:
                handle_joystick_events(event)
                # Botón OPTIONS = pausa
                if event.type == pygame.JOYBUTTONDOWN and event.button in pause_buttons:
                    menu_sound.play()
                    result = pause_menu()
                    if result == "menu":
                        return  # salimos al menú principal

            # Pausa con teclado
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_p, pygame.K_ESCAPE):
                    menu_sound.play()
                    result = pause_menu()
                    if result == "menu":
                        return

        # Controles
        keys = pygame.key.get_pressed()

        # Player 1 (control PS5 si hay, si no, teclado W/S)
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
            if p2_y + PADDLE_H / 2 < ball_y:
                p2_y += cpu_speed
            elif p2_y + PADDLE_H / 2 > ball_y:
                p2_y -= cpu_speed
        else:  # 2 jugadores (flechas)
            if keys[pygame.K_UP]:
                p2_y -= 7
            if keys[pygame.K_DOWN]:
                p2_y += 7

        # Limitar paletas
        p1_y = max(0, min(HEIGHT - PADDLE_H, p1_y))
        p2_y = max(0, min(HEIGHT - PADDLE_H, p2_y))

        # Movimiento pelota
        ball_x += ball_vx
        ball_y += ball_vy

        # Rebotes verticales
        if ball_y <= 0 or ball_y >= HEIGHT - BALL_SIZE:
            ball_vy *= -1
            hit_sound.play()

        # Colisión con paletas
        # Izquierda
        if ball_x <= 60 + PADDLE_W:
            if p1_y <= ball_y <= p1_y + PADDLE_H:
                ball_vx *= -1
                hit_sound.play()
                score += 1
            else:
                # Punto en contra
                ball_x, ball_y = WIDTH // 2, HEIGHT // 2
                ball_vx = 6
                ball_vy = 6
                score = 0
                point_sound.play()

        # Derecha
        if ball_x >= WIDTH - 60 - PADDLE_W - BALL_SIZE:
            if p2_y <= ball_y <= p2_y + PADDLE_H:
                ball_vx *= -1
                hit_sound.play()
            else:
                ball_x, ball_y = WIDTH // 2, HEIGHT // 2
                ball_vx = -6
                ball_vy = 6
                score = 0
                point_sound.play()

        # ----------------- DIBUJAR (nuevo layout: izquierda=eventos, centro=juego, derecha=control) -----------------
        # Superficie de juego (igual lógica que antes)
        game_surf = pygame.Surface((WIDTH, HEIGHT))
        game_surf.fill((0,0,0))

        # Score (centrado en área de juego)
        txt = font.render(f"SCORE: {score}", True, (255, 255, 255))
        game_surf.blit(txt, (WIDTH // 2 - txt.get_width() // 2, 10))

        # Paletas y pelota (en game_surf coordenadas)
        pygame.draw.rect(game_surf, (255, 255, 255), (60, p1_y, PADDLE_W, PADDLE_H))
        pygame.draw.rect(game_surf, (255, 255, 255), (WIDTH - 60 - PADDLE_W, p2_y, PADDLE_W, PADDLE_H))
        pygame.draw.rect(game_surf, (255, 255, 255), (ball_x, ball_y, BALL_SIZE, BALL_SIZE))

        # Blit de game_surf en la ventana principal (offset por panel izquierdo)
        screen.fill((12,12,16))
        # Panel izquierdo fondo
        pygame.draw.rect(screen, (18,18,22), (0, 0, LEFT_PANEL_W, SCREEN_H))
        # Si el layout es 'right' mantenemos el panel derecho oscuro.
        # Si es 'bottom', no dibujamos la franja derecha para que el área
        # inferior (control) pueda usar todo el ancho disponible.
        if CONTROLLER_LAYOUT == 'right':
            pygame.draw.rect(screen, (18,18,22), (LEFT_PANEL_W + WIDTH, 0, RIGHT_PANEL_W, SCREEN_H))
        else:
            # En bottom layout dibujamos una franja inferior (footer) para el mando
            # que ocupa el ancho restante, evitando la banda vacía a la derecha.
            footer_x = LEFT_PANEL_W
            footer_w = SCREEN_W - LEFT_PANEL_W
            pygame.draw.rect(screen, (16,16,20), (footer_x, HEIGHT, footer_w, CONTROLLER_H))

        screen.blit(game_surf, (LEFT_PANEL_W, 0))

        # --- Panel izquierdo: eventos y ejes ---
        lx = 12
        y = 12
        lt = font.render("EVENTOS HID (kernel → pygame)", True, (0, 200, 255))
        screen.blit(lt, (lx, y))
        y += 34
        for line in event_log[-12:]:
            t = small_font.render(line, True, (0, 255, 0))
            screen.blit(t, (lx, y))
            y += 18

        # Ejes
        ay = 12
        at = font.render("Ejes HID (estado actual)", True, (255, 220, 0))
        screen.blit(at, (lx, y + 8))
        ax_y = y + 40
        for idx, val in axis_states.items():
            label = AXIS_LABELS.get(idx, f"AXIS_{idx}")
            t = small_font.render(f"{label}: {val:+.2f}", True, (220, 220, 220))
            screen.blit(t, (lx, ax_y))
            ax_y += 18

        # Mostrar botón(s) de pausa asignado(s) en panel izquierdo (abajo)
        try:
            pause_txt = ", ".join([f"B{b}" for b in pause_buttons])
        except Exception:
            pause_txt = "-"
        p_label = small_font.render(f"Pausa: {pause_txt}", True, (180, 180, 255))
        screen.blit(p_label, (12, SCREEN_H - 28))

        # --- Dibujar DualSense según layout seleccionado ---
        if CONTROLLER_LAYOUT == 'right':
            ctrl_cx = LEFT_PANEL_W + WIDTH + (RIGHT_PANEL_W // 2)
            ctrl_cy = SCREEN_H // 2
            draw_dualsense_minimal(screen, ctrl_cx, ctrl_cy, axis_states, button_states, max_width=RIGHT_PANEL_W, max_height=SCREEN_H - 20)
        else:  # 'bottom'
            # Permitir que el controlador use todo el ancho disponible (desde el borde izquierdo)
            # para eliminar la franja vacía de la derecha y aumentar el tamaño.
            ctrl_area_w = SCREEN_W - 24
            ctrl_cx = SCREEN_W // 2
            # vertical: justo en la franja inferior reservada
            ctrl_cy = HEIGHT + (CONTROLLER_H // 2)
            draw_dualsense_minimal(screen, ctrl_cx, ctrl_cy, axis_states, button_states, max_width=ctrl_area_w, max_height=CONTROLLER_H - 12)

        pygame.display.flip()
        clock.tick(60)

# ----------------- MAIN LOOP -----------------
if __name__ == "__main__":
    while True:
        option = menu_loop()  # 0 = 1P, 1 = 2P, 2 = salir
        if option == 0:
            game_loop(mode=0)
        elif option == 1:
            game_loop(mode=1)
        else:
            pygame.quit()
            sys.exit()
