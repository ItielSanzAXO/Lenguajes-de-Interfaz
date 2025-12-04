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
INFO_HEIGHT = 250
screen = pygame.display.set_mode((WIDTH, HEIGHT + INFO_HEIGHT))
pygame.display.set_caption("Pong Final - Menú, Pausa, DualSense Minimalista")

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
def draw_dualsense_minimal(surface, center_x, center_y, axes, btns):
    # Cuerpo principal
    body_rect = pygame.Rect(center_x - 150, center_y - 45, 300, 110)
    pygame.draw.ellipse(surface, (235, 235, 235), body_rect)
    pygame.draw.ellipse(surface, (40, 40, 40), body_rect, 3)

    # "alas" laterales para agarres
    left_grip = pygame.Rect(center_x - 190, center_y - 10, 90, 90)
    right_grip = pygame.Rect(center_x + 100, center_y - 10, 90, 90)
    pygame.draw.ellipse(surface, (220, 220, 220), left_grip)
    pygame.draw.ellipse(surface, (220, 220, 220), right_grip)

    # Touchpad minimal
    pad_rect = pygame.Rect(center_x - 70, center_y - 30, 140, 45)
    pygame.draw.rect(surface, (45, 45, 45), pad_rect, border_radius=10)

    # Barra de luz superior
    light_rect = pygame.Rect(center_x - 40, center_y - 45, 80, 6)
    pygame.draw.rect(surface, (80,140,255), light_rect, border_radius=3)

    # Sticks
    lsx = axes.get(0, 0.0)
    lsy = axes.get(1, 0.0)
    rsx = axes.get(2, 0.0)
    rsy = axes.get(3, 0.0)

    # Left stick
    ls_center = (center_x - 70, center_y + 15)
    pygame.draw.circle(surface, (50, 50, 50), ls_center, 18)
    pygame.draw.circle(
        surface,
        (200, 200, 200),
        (int(ls_center[0] + lsx * 8), int(ls_center[1] + lsy * 8)),
        10
    )
    # Right stick
    rs_center = (center_x + 70, center_y + 25)
    pygame.draw.circle(surface, (50, 50, 50), rs_center, 18)
    pygame.draw.circle(
        surface,
        (200, 200, 200),
        (int(rs_center[0] + rsx * 8), int(rs_center[1] + rsy * 8)),
        10
    )

    # Botones frontales minimalistas
    face_buttons = {
        0: ("X", (center_x + 115, center_y + 30), (70, 120, 255)),
        1: ("O", (center_x + 140, center_y + 5), (255, 70, 70)),
        2: ("□", (center_x + 90, center_y + 5), (255, 180, 200)),
        3: ("△", (center_x + 115, center_y - 20), (100, 255, 100)),
    }

    for idx, (symbol, (bx, by), color) in face_buttons.items():
        pressed = btns.get(idx, False)
        fill = color if pressed else (190, 190, 190)
        pygame.draw.circle(surface, fill, (bx, by), 11)
        pygame.draw.circle(surface, (0, 0, 0), (bx, by), 11, 2)
        t = small_font.render(symbol, True, (0, 0, 0))
        surface.blit(t, (bx - t.get_width() // 2, by - t.get_height() // 2))

    # L1 / R1
    l1_pressed = btns.get(4, False)
    r1_pressed = btns.get(5, False)
    l1_rect = pygame.Rect(center_x - 130, center_y - 50, 55, 12)
    r1_rect = pygame.Rect(center_x + 75, center_y - 50, 55, 12)
    pygame.draw.rect(surface, (160,160,160) if l1_pressed else (110,110,110), l1_rect, border_radius=4)
    pygame.draw.rect(surface, (160,160,160) if r1_pressed else (110,110,110), r1_rect, border_radius=4)

    # Etiqueta
    label = small_font.render("DualSense (vista lógica / minimalista)", True, (230, 230, 230))
    surface.blit(label, (center_x - label.get_width() // 2, center_y + 55))


# ----------------- MENÚ PRINCIPAL -----------------
def draw_menu(selected_index):
    screen.fill((5, 5, 10))

    title = big_font.render("P O N G", True, (255, 255, 255))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 80))

    options = ["1 Jugador (vs CPU)", "2 Jugadores", "Salir"]
    for i, text in enumerate(options):
        color = (255, 255, 0) if i == selected_index else (200, 200, 200)
        t = font.render(text, True, color)
        screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 200 + i * 60))

    info = small_font.render("Mover: ↑/↓ o Stick | Seleccionar: Enter o X", True, (150, 150, 150))
    screen.blit(info, (WIDTH // 2 - info.get_width() // 2, HEIGHT - 40))

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
        # Dibujar overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        title = big_font.render("PAUSADO", True, (255, 255, 255))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 140))

        options = ["Reanudar", "Salir al menú"]
        for i, txt in enumerate(options):
            color = (255, 255, 0) if i == selected else (220, 220, 220)
            t = font.render(txt, True, color)
            screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 220 + i * 50))

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
                    if event.button == 9:  # Options también reanuda
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

        # ----------------- DIBUJAR -----------------
        screen.fill((0, 0, 0))

        # Score
        txt = font.render(f"SCORE: {score}", True, (255, 255, 255))
        screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, 10))

        # Paletas y pelota
        pygame.draw.rect(screen, (255, 255, 255), (60, p1_y, PADDLE_W, PADDLE_H))
        pygame.draw.rect(screen, (255, 255, 255),
                         (WIDTH - 60 - PADDLE_W, p2_y, PADDLE_W, PADDLE_H))
        pygame.draw.rect(screen, (255, 255, 255),
                         (ball_x, ball_y, BALL_SIZE, BALL_SIZE))

        # Panel técnico inferior
        pygame.draw.rect(screen, (15, 15, 20), (0, HEIGHT, WIDTH, INFO_HEIGHT))
        pygame.draw.rect(screen, (80, 80, 90), (0, HEIGHT, WIDTH, INFO_HEIGHT), 3)

        # LOG izquierda
        y = HEIGHT + 10
        lt = font.render("EVENTOS HID (kernel → pygame)", True, (0, 200, 255))
        screen.blit(lt, (10, y))
        y += 30
        for line in event_log:
            t = small_font.render(line, True, (0, 255, 0))
            screen.blit(t, (10, y))
            y += 18

        # Ejes HID centro
        ax_y = HEIGHT + 10
        at = font.render("Ejes HID (estado actual)", True, (255, 220, 0))
        screen.blit(at, (350, ax_y))
        ax_y += 30
        for idx, val in axis_states.items():
            label = AXIS_LABELS.get(idx, f"AXIS_{idx}")
            t = small_font.render(f"{label}: {val:+.2f}", True, (220, 220, 220))
            screen.blit(t, (350, ax_y))
            ax_y += 22

        # Control DualSense minimalista derecha
        draw_dualsense_minimal(screen, WIDTH - 200, HEIGHT + 120, axis_states, button_states)

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
