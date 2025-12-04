import pygame
import sys
import random

pygame.init()
pygame.joystick.init()
pygame.mixer.init()

# ---------------- Detectar Control ----------------
use_controller = False
if pygame.joystick.get_count() > 0:
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    use_controller = True
    print("Control PS5 detectado:", joystick.get_name())
else:
    print("No hay control; solo teclado disponible para 2P.")

# ---------------- Pantalla ------------------------
WIDTH, HEIGHT = 900, 600
INFO_HEIGHT = 250
screen = pygame.display.set_mode((WIDTH, HEIGHT + INFO_HEIGHT))
pygame.display.set_caption("Pong (Menú + Sonidos + 1P/2P + HID Panel + DualSense UI)")

clock = pygame.time.Clock()

# ---------------- Sonidos -------------------------
hit_sound = pygame.mixer.Sound("pong_hit.wav")
point_sound = pygame.mixer.Sound("pong_point.wav")
menu_sound = pygame.mixer.Sound("menu_select.wav")

# ---------------- Juego ------------------
paddle_width = 15
paddle_height = 90

ball_size = 14
font = pygame.font.SysFont("Consolas", 22, bold=True)
big_font = pygame.font.SysFont("Consolas", 40, bold=True)
small_font = pygame.font.SysFont("Consolas", 16)

# ---------------- Mapeos HID ------------------
AXIS_LABELS = {
    0: "ABS_X  (Left Stick X)",
    1: "ABS_Y  (Left Stick Y)",
    2: "ABS_Z  (Right Stick X / L2)",
    3: "ABS_RZ (Right Stick Y / R2)"
}

BUTTON_LABELS = {
    0: "BTN_SOUTH (X)",
    1: "BTN_EAST (Circle)",
    2: "BTN_WEST (Square)",
    3: "BTN_NORTH (Triangle)",
    4: "L1", 5: "R1", 6: "L2", 7: "R2",
    8: "Share", 9: "Options",
    10: "L3", 11: "R3",
}

axis_states = {}
button_states = {}
event_log = []
MAX_LOG = 8

def log_event(text):
    event_log.append(text)
    if len(event_log) > MAX_LOG:
        event_log.pop(0)

# ---------------- Dibujar Control ------------------
def draw_controller(surface, x, y, axes, btns):
    pygame.draw.ellipse(surface, (90, 90, 90), (x - 150, y - 50, 300, 120))
    pygame.draw.ellipse(surface, (25, 25, 25), (x - 150, y - 50, 300, 120), 3)

    # STICKS
    lsx = axes.get(0, 0.0)
    lsy = axes.get(1, 0.0)
    rsx = axes.get(2, 0.0)
    rsy = axes.get(3, 0.0)

    pygame.draw.circle(surface, (40, 40, 40), (x - 70, y + 10), 25)
    pygame.draw.circle(surface, (180, 180, 180),
                       (int(x - 70 + lsx * 10), int(y + 10 + lsy * 10)), 14)

    pygame.draw.circle(surface, (40, 40, 40), (x + 70, y + 20), 25)
    pygame.draw.circle(surface, (180, 180, 180),
                       (int(x + 70 + rsx * 10), int(y + 20 + rsy * 10)), 14)

    # BOTONES PS
    face_buttons = {
        0: ("X", (x + 110, y + 30), (70,120,255)),
        1: ("O", (x + 135, y + 5), (255,70,70)),
        2: ("□", (x + 85, y + 5), (255,180,200)),
        3: ("△", (x + 110, y - 20), (100,255,100)),
    }

    for idx, (symbol, (bx, by), color) in face_buttons.items():
        pressed = btns.get(idx, False)
        fill = color if pressed else (150,150,150)

        pygame.draw.circle(surface, fill, (bx, by), 12)
        pygame.draw.circle(surface, (0,0,0), (bx, by), 12, 2)

        t = small_font.render(symbol, True, (0,0,0))
        surface.blit(t, (bx - t.get_width()//2, by - t.get_height()//2))

# ---------------- Función de menú ------------------
def draw_menu(selected):
    screen.fill((0, 0, 0))
    title = big_font.render("P O N G", True, (255,255,255))
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

    options = ["1 Jugador", "2 Jugadores", "Salir"]

    for i, option in enumerate(options):
        color = (255,255,0) if i == selected else (180,180,180)
        t = font.render(option, True, color)
        screen.blit(t, (WIDTH//2 - t.get_width()//2, 200 + i*60))

    pygame.display.flip()

def menu_loop():
    selected = 0
    while True:
        draw_menu(selected)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % 3
                    menu_sound.play()
                if event.key == pygame.K_DOWN:
                    selected = (selected + 1) % 3
                    menu_sound.play()
                if event.key == pygame.K_RETURN:
                    menu_sound.play()
                    return selected

            if use_controller:
                if event.type == pygame.JOYAXISMOTION:
                    if event.axis == 1 and event.value > 0.5:
                        selected = (selected + 1) % 3
                        menu_sound.play()
                    if event.axis == 1 and event.value < -0.5:
                        selected = (selected - 1) % 3
                        menu_sound.play()

                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:  # X
                        menu_sound.play()
                        return selected

# ---------------- Loop de Juego ------------------
def game_loop(mode):
    global axis_states, button_states

    paddle1_y = HEIGHT // 2
    paddle2_y = HEIGHT // 2

    ball_x = WIDTH//2
    ball_y = HEIGHT//2
    ball_speed_x = 6
    ball_speed_y = 6

    score = 0
    cpu_speed = 6

    # Inicializar HID
    if use_controller:
        axis_states = {i: 0.0 for i in range(joystick.get_numaxes())}
        button_states = {i: False for i in range(joystick.get_numbuttons())}

    while True:
        # EVENTOS
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if use_controller:
                if event.type == pygame.JOYBUTTONDOWN:
                    btn = event.button
                    button_states[btn] = True
                    log_event(f"[BTN ↓] {BUTTON_LABELS.get(btn,btn)}")

                if event.type == pygame.JOYBUTTONUP:
                    btn = event.button
                    button_states[btn] = False
                    log_event(f"[BTN ↑] {BUTTON_LABELS.get(btn,btn)}")

                if event.type == pygame.JOYAXISMOTION:
                    axis = event.axis
                    val = joystick.get_axis(axis)
                    axis_states[axis] = val
                    log_event(f"[AXIS] {AXIS_LABELS.get(axis,axis)} = {val:.2f}")

        # CONTROLES
        keys = pygame.key.get_pressed()

        # PLAYER 1 (CON PS5)
        if use_controller:
            ly = axis_states.get(1, 0)
            if abs(ly) > 0.2:
                paddle1_y += ly * 7

        # PLAYER 2
        if mode == 1:  # CPU
            if paddle2_y < ball_y:
                paddle2_y += cpu_speed
            else:
                paddle2_y -= cpu_speed
        else:  # 2 jugadores (teclado)
            if keys[pygame.K_UP]:
                paddle2_y -= 7
            if keys[pygame.K_DOWN]:
                paddle2_y += 7

        paddle1_y = max(0, min(HEIGHT - paddle_height, paddle1_y))
        paddle2_y = max(0, min(HEIGHT - paddle_height, paddle2_y))

        # MOVIMIENTO PELOTA
        ball_x += ball_speed_x
        ball_y += ball_speed_y

        if ball_y <= 0 or ball_y >= HEIGHT - ball_size:
            ball_speed_y *= -1
            hit_sound.play()

        if ball_x <= 60 + paddle_width:
            if paddle1_y <= ball_y <= paddle1_y + paddle_height:
                ball_speed_x *= -1
                hit_sound.play()
                score += 1
            else:
                ball_x, ball_y = WIDTH//2, HEIGHT//2
                score = 0
                point_sound.play()

        if ball_x >= WIDTH - 60 - paddle_width:
            if paddle2_y <= ball_y <= paddle2_y + paddle_height:
                ball_speed_x *= -1
                hit_sound.play()
            else:
                ball_x, ball_y = WIDTH//2, HEIGHT//2
                score = 0
                point_sound.play()

        # ---------- DIBUJAR ----------
        screen.fill((0,0,0))

        # SCORE
        s = font.render(f"SCORE: {score}", True, (255,255,255))
        screen.blit(s, (WIDTH//2 - s.get_width()//2, 10))

        # PALETAS Y PELOTA
        pygame.draw.rect(screen, (255,255,255), (60, paddle1_y, paddle_width, paddle_height))
        pygame.draw.rect(screen, (255,255,255), (WIDTH-60-paddle_width, paddle2_y, paddle_width, paddle_height))
        pygame.draw.rect(screen, (255,255,255), (ball_x, ball_y, ball_size, ball_size))

        # PANEL TÉCNICO
        pygame.draw.rect(screen, (20,20,20), (0, HEIGHT, WIDTH, INFO_HEIGHT))
        pygame.draw.rect(screen, (80,80,80), (0, HEIGHT, WIDTH, INFO_HEIGHT), 3)

        # LOG (izquierda)
        y = HEIGHT + 10
        lt = font.render("EVENTOS HID", True, (0,200,255))
        screen.blit(lt, (10, y))
        y += 30
        for line in event_log:
            t = small_font.render(line, True, (0,255,0))
            screen.blit(t, (10, y))
            y += 18

        # Ejes HID (medio)
        ax_y = HEIGHT + 10
        at = font.render("EJES HID", True, (255,220,0))
        screen.blit(at, (350, ax_y))
        ax_y += 30
        for idx, val in axis_states.items():
            label = AXIS_LABELS.get(idx, f"AXIS_{idx}")
            t = small_font.render(f"{label}: {val:+.2f}", True, (220,220,220))
            screen.blit(t, (350, ax_y))
            ax_y += 22

        # CONTROL DUALSENSE (derecha)
        draw_controller(screen, WIDTH - 200, HEIGHT + 120, axis_states, button_states)

        pygame.display.flip()
        clock.tick(60)

# ---------------------------------------------------
# ---------------- EJECUCIÓN PRINCIPAL --------------
# ---------------------------------------------------
while True:
    opt = menu_loop()

    if opt == 0:
        game_loop(mode=1)  # 1 jugador
    elif opt == 1:
        game_loop(mode=2)  # 2 jugadores
    else:
        pygame.quit()
        sys.exit()