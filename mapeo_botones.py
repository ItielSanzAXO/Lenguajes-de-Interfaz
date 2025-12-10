import pygame
import sys

# Inicializar Pygame
pygame.init()
pygame.joystick.init()

# Crear ventana simple
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Mapeo de Botones PS5 - Presiona los botones del D-Pad")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Consolas", 24, bold=True)
big_font = pygame.font.SysFont("Consolas", 32, bold=True)

# Detectar control
if pygame.joystick.get_count() > 0:
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Control detectado: {joystick.get_name()}")
    print(f"Botones: {joystick.get_numbuttons()}")
    print(f"Ejes: {joystick.get_numaxes()}")
    print(f"HATs: {joystick.get_numhats()}")
else:
    print("No hay control detectado")
    pygame.quit()
    sys.exit()

# Diccionario de botones presionados
buttons_pressed = {}
hat_state = None
button_log = []

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        if event.type == pygame.JOYBUTTONDOWN:
            button_log.append(f"BOTÓN PRESIONADO: {event.button}")
            buttons_pressed[event.button] = pygame.time.get_ticks()
            print(f"Botón {event.button} presionado")
        
        if event.type == pygame.JOYBUTTONUP:
            button_log.append(f"BOTÓN SOLTADO: {event.button}")
            if event.button in buttons_pressed:
                del buttons_pressed[event.button]
            print(f"Botón {event.button} soltado")
        
        if event.type == pygame.JOYHATMOTION:
            hat_state = event.value
            button_log.append(f"D-PAD: {event.value}")
            print(f"D-Pad: {event.value}")

    # Limpiar pantalla
    screen.fill((10, 10, 20))
    
    # Título
    title = big_font.render("MAPEO DE BOTONES PS5", True, (255, 255, 0))
    screen.blit(title, (150, 50))
    
    # Instrucciones
    inst1 = font.render("Presiona los botones del D-Pad (arriba, abajo, izquierda, derecha)", True, (200, 200, 200))
    screen.blit(inst1, (50, 150))
    
    inst2 = font.render("También presiona X, Circle, Square, Triangle para verificar", True, (200, 200, 200))
    screen.blit(inst2, (50, 200))
    
    # Estado actual del D-Pad
    if hat_state:
        hat_text = f"D-Pad Actual: {hat_state}"
        hat_x, hat_y = hat_state
        if hat_y == 1:
            hat_text += " (ARRIBA)"
        elif hat_y == -1:
            hat_text += " (ABAJO)"
        elif hat_x == -1:
            hat_text += " (IZQUIERDA)"
        elif hat_x == 1:
            hat_text += " (DERECHA)"
        hat_display = font.render(hat_text, True, (100, 255, 100))
        screen.blit(hat_display, (50, 280))
    
    # Botones presionados
    buttons_text = f"Botones presionados: {list(buttons_pressed.keys())}"
    buttons_display = font.render(buttons_text, True, (100, 150, 255))
    screen.blit(buttons_display, (50, 330))
    
    # Log de eventos
    log_y = 400
    log_title = font.render("Últimos eventos:", True, (255, 200, 100))
    screen.blit(log_title, (50, log_y))
    
    log_y += 40
    for line in button_log[-8:]:
        log_text = font.render(line, True, (200, 200, 200))
        screen.blit(log_text, (70, log_y))
        log_y += 30
    
    # Info para salir
    exit_text = font.render("Presiona ESC o cierra la ventana para salir", True, (150, 150, 150))
    screen.blit(exit_text, (50, 580))
    
    # Evento de teclado para salir
    keys = pygame.key.get_pressed()
    if keys[pygame.K_ESCAPE]:
        running = False
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
print("\nResumen:")
print("Si ves 'D-Pad: (0, -1)' cuando presionas ARRIBA -> D-Pad está funcionando correctamente")
print("Si ves números de botones para el D-Pad -> necesitamos mapear esos botones en el código")
