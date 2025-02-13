from ursina import *
from random import randint
import time


def update():
    global invaders, bullets, score, last_time, game_over

    if game_over:
        return

    # Invader movement and collision with the player
    for invader in invaders:
        invader.y += time.dt * invader.dy

        if invader.intersects(player).hit:
            end_game()
            return

        if invader.y <= -0.5:
            reset_invader(invader)

    # Bullet movement and collision with invaders
    for bullet in bullets:
        bullet.y += time.dt * bullet.dy
        hit_info = bullet.intersects()
        if hit_info.hit:
            Audio('assets/explosion_sound.wav')
            bullet.x = 10
            score += 1
            text.text = f"Score: {score}"

            if hit_info.entity in invaders:
                reset_invader(hit_info.entity)

    current_time = time.time()
    if current_time - last_time >= 1:
        score += 12
        text.text = f"Score: {score}"
        last_time = current_time


def input(key):
    global bullets, current_lane

    if game_over:
        return

    if key == "space":
        Audio('assets/laser_sound.wav')
        bullet = Bullet()
        bullets.append(bullet)

    # Player movement between lanes
    if key == "left arrow" and current_lane > 0:
        current_lane -= 1
        player.x = lanes[current_lane]

    elif key == "right arrow" and current_lane < 2:
        current_lane += 1
        player.x = lanes[current_lane]


def reset_invader(invader):
    invader.x = lanes[randint(0, 2)]  # Place invader in one of the three lanes
    invader.y = randint(80, 120) * 0.01


def end_game():
    global game_over
    game_over = True

    Text(text='Game Over', origin=(0, 0), scale=3, color=color.red, position=(0, 0.1), background=True)
    Text(text=f'Final Score: {score}', origin=(0, 0), scale=2, color=color.yellow, position=(0, -0.1), background=True)


class Invader(Entity):
    def __init__(self):
        super().__init__()
        self.parent = field
        self.model = 'quad'
        self.texture = 'alien.png'
        self.scale = 0.1
        self.position = (lanes[randint(0, 2)], randint(80, 120) * 0.01, -0.1)
        self.collider = 'box'
        self.dy = -0.30
        self.collider = BoxCollider(self, size=(0.08, 0.08, 0))


class Player(Entity):
    def __init__(self):
        super().__init__()
        self.parent = field
        self.model = 'quad'
        self.texture = 'assets/player.png'
        self.scale = (0.2, 0.2, 0)
        self.position = (0, -0.5, -0.1)
        self.collider = BoxCollider(self, size=(0.15, 0.18, 0))


class Bullet(Entity):
    def __init__(self):
        super().__init__()
        self.parent = field
        self.model = 'cube'
        self.color = color.green
        self.texture = 'assets/laser'
        self.scale = (0.02, 0.1, 0.1)
        self.position = player.position
        self.y = player.y + 0.2
        self.collider = 'box'
        self.dy = 0.8


app = Ursina()

# Define the three lanes (x-coordinates)
lanes = [-0.5, 0, 0.5]
current_lane = 1  # Start player in the middle lane

field_size = 19
Entity(model='quad', scale=60, texture='assets/blue_sky')
field = Entity(model='quad', color=color.rgba(255, 255, 255, 0), scale=(12, 18),
               position=(field_size // 2, field_size // 2, -0.01))

bullets = []
invaders = []

player = Player()
player.x = lanes[current_lane]

for i in range(5):
    invader = Invader()
    invaders.append(invader)

score = 0
last_time = time.time()

game_over = False

text = Text(text='Score: 0', position=(-0.65, 0.4), origin=(0, 0), scale=2, color=color.yellow, background=True)

camera.position = (field_size // 2, -18, -18)
camera.rotation_x = -56

app.run()
