from ursina import *
from random import randint, choice, sample
import time
import os
import sys 
from subprocess import call
import json
import websockets
import asyncio
from concurrent.futures import ThreadPoolExecutor
import socket

from email.mime import audio
from ursina import *
from random import randint, choice, sample
import time
import cv2
import mediapipe as mp
import numpy as np
import threading
from PIL import Image
import io
from multiprocessing import Process, Value
import ctypes

# Set environment variable to skip camera authorization request
os.environ["OPENCV_AVFOUNDATION_SKIP_AUTH"] = "1"

# Initialize MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils

# Add these global variables near the start
running = True
cap = None

# MacOS-specific camera permission handling
def check_camera_permission():
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Camera access not authorized. Please grant permission in System Preferences.")
            call(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"])  # Open system preferences
            return False
        cap.release()
        return True
    except Exception as e:
        print(f"Error checking camera permission: {e}")
        return False

# Initialize MediaPipe with error handling
def init_mediapipe():
    try:
        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        return mp_hands, hands
    except Exception as e:
        print(f"Error initializing MediaPipe: {e}")
        return None, None

# Global variables
running = True
mp_hands, hands = init_mediapipe()
mp_draw = mp.solutions.drawing_utils

class CameraPreview(Entity):
    def __init__(self):
        super().__init__()
        self.parent = camera.ui
        self.model = 'quad'
        self.texture = None
        self.scale = (0.3, 0.2)
        self.position = Vec2(0.7, 0.3)
        self.always_on_top = True

class HandGestureController:
    def __init__(self):
        self.running = Value(ctypes.c_bool, True)
        self.movement = Value(ctypes.c_int, 0)  # -1 for left, 0 for neutral, 1 for right
        self.shoot = Value(ctypes.c_bool, False)
        self.restart = Value(ctypes.c_bool, False)
        self.last_shoot = False
        self.process = None

    def camera_process(self, running, movement, shoot, restart):
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("Failed to open camera")
                return

            cv2.namedWindow('Hand Controls', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Hand Controls', 400, 300)
            cv2.moveWindow('Hand Controls', 100, 100)

            while running.value:
                success, image = cap.read()
                if not success:
                    continue

                image = cv2.resize(image, (400, 300))
                image = cv2.flip(image, 1)
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                results = hands.process(image_rgb)

                h, w, _ = image.shape
                # Draw control zone lines
                left_boundary = w * 0.3
                right_boundary = w * 0.7
                
                cv2.line(image, (int(left_boundary), 0), (int(left_boundary), h), (255, 0, 0), 2)
                cv2.line(image, (int(right_boundary), 0), (int(right_boundary), h), (255, 0, 0), 2)

                # Reset to center if no hands detected
                if not results.multi_hand_landmarks:
                    movement.value = 0  # Center position
                    shoot.value = False

                if results.multi_hand_landmarks:
                    # Process single hand controls
                    hand_landmarks = results.multi_hand_landmarks[0]
                    mp_draw.draw_landmarks(
                        image,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS
                    )

                    # Get wrist and middle finger tip for hand raise detection
                    wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                    middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                    index_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
                    thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]

                    # Check if hand is raised (middle finger tip above wrist)
                    hand_raised = middle_tip.y < wrist.y - 0.1  # Added threshold for more reliable detection
                    
                    # Determine position based on raised hand position
                    x_pos = index_tip.x
                    if hand_raised:
                        if x_pos < 0.3:  # Left zone
                            movement.value = -1
                        elif x_pos > 0.7:  # Right zone
                            movement.value = 1
                    else:
                        movement.value = 0  # Return to center when hand is lowered

                    # Process pinch for shooting
                    pinch_distance = np.sqrt(
                        (thumb_tip.x - index_tip.x)**2 +
                        (thumb_tip.y - index_tip.y)**2
                    )
                    shoot.value = pinch_distance < 0.1

                    # Add visual indicators
                    position_text = "LEFT" if movement.value == -1 else "RIGHT" if movement.value == 1 else "CENTER"
                    cv2.putText(image, f"Position: {position_text}", (w//2 - 50, 30),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(image, f"Hand Raised: {hand_raised}", (10, 120),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # Add visual feedback for shooting
                cv2.putText(image, f"Shoot: {shoot.value}", (10, 60),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                cv2.imshow('Hand Controls', image)
                if cv2.waitKey(1) & 0xFF == 27:
                    running.value = False

                time.sleep(0.016)

        except Exception as e:
            print(f"Camera process error: {e}")
        finally:
            if cap is not None:
                cap.release()
            cv2.destroyAllWindows()

    def start(self):
        self.process = Process(target=self.camera_process, 
                             args=(self.running, self.movement, self.shoot, self.restart))
        self.process.start()

    def stop(self):
        self.running.value = False
        if self.process:
            self.process.join()

class WebSocketClient:
    def __init__(self):
        self.uri = "ws://0.tcp.in.ngrok.io:12989/ws"  # Updated to use ngrok server
        self.websocket = None
        self.running = True
        self.thread = threading.Thread(target=self.run_websocket_client)
        self.thread.daemon = True

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            print("Connected to WebSocket server")
            while self.running:
                try:
                    message = await self.websocket.recv()
                    if message == "reset_acknowledged":
                        print("Received reset command")
                        invoke(restart_game)
                except websockets.ConnectionClosed:
                    print("WebSocket connection closed. Attempting to reconnect...")
                    try:
                        self.websocket = await websockets.connect(self.uri)
                        print("Reconnected to WebSocket server")
                    except:
                        print("Failed to reconnect")
                        break
        except Exception as e:
            print(f"WebSocket error: {e}")

    def run_websocket_client(self):
        asyncio.run(self.connect())

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False
        if self.websocket:
            asyncio.run(self.websocket.close())

def restart_game():
    global score, game_over, bullet_count, current_lane, invaders, bullets, ammo
    
    # Reset game state
    game_over = False
    score = 0
    bullet_count = max_bullets
    current_lane = 1
    
    # Reset player position
    player.x = lanes[current_lane]
    
    # Clear existing entities
    for bullet in bullets:
        destroy(bullet)
    for invader in invaders:
        destroy(invader)
    for ammo_item in ammo:
        destroy(ammo_item)
    
    # Clear lists
    bullets.clear()
    invaders.clear()
    ammo.clear()
    
    # Create new invaders
    for i in range(5):
        invader = Invader()
        invaders.append(invader)
    
    # Create new ammo items
    for i in range(3):
        ammo_item = Ammo()
        ammo.append(ammo_item)
    
    # Reset score and ammo display
    score_text.text = 'Score: 0'
    ammo_text.text = f"Ammo: {bullet_count}"
    
    # Find and destroy all game over related text entities
    entities_to_destroy = []
    for entity in scene.entities:
        if isinstance(entity, Text):
            if entity != score_text and entity != ammo_text:  # Don't destroy score and ammo text
                entities_to_destroy.append(entity)
    
    # Destroy the collected entities
    for entity in entities_to_destroy:
        destroy(entity)
    
    # Reset score in player file
    if 'player_id' in globals():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            host = '0.tcp.in.ngrok.io'
            port = 12989
            sock.connect((host, port))
            score_data = f"player_id:{score}"
            sock.send(bytes(score_data, 'utf-8'))
            sock.close()
        except Exception as e:
            print(f"Error sending score: {e}")


def update():
    global invaders, bullets, score, last_time, game_over, locked_lane, max_bullets, bullet_count, controller, current_lane

    # Check for restart gesture
    if controller.restart.value and game_over:
        restart_game()
        return

    if game_over:
        return

    # Handle hand gesture controls
    if controller.movement.value == -1:  # Left
        current_lane = 0
        player.x = lanes[current_lane]
    elif controller.movement.value == 1:  # Right
        current_lane = 2
        player.x = lanes[current_lane]
    else:  # Center
        current_lane = 1
        player.x = lanes[current_lane]

    # Handle shooting with cooldown
    if controller.shoot.value and not controller.last_shoot and bullet_count > 0:
        Audio('assets/laser_sound.wav')
        bullet = Bullet()
        bullets.append(bullet)
        bullet_count -= 1
    controller.last_shoot = controller.shoot.value

    # Update ammo count display
    ammo_text.text = f"Ammo: {bullet_count}"

    # Update invaders
    for invader in invaders:
        invader.y += time.dt * invader.dy

        if invader.intersects(player).hit:
            end_game()
            return

        if invader.y <= -0.5:
            reset_invader(invader)

    # Update bullets
    for bullet in bullets:
        bullet.y += time.dt * bullet.dy
        hit_info = bullet.intersects()
        if hit_info.hit:
            Audio('assets/medium-explosion-40472.mp3')
            bullet.x = 10
            score += 10
            score_text.text = f"Score: {score}"
            
            # Update score file immediately when score changes
            if 'player_id' in globals():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    host = '0.tcp.in.ngrok.io'
                    port = 12989
                    sock.connect((host, port))
                    score_data = f"{player_id}:{score}"
                    sock.send(bytes(score_data, 'utf-8'))
                    sock.close()
                except Exception as e:
                    print(f"Error sending score: {e}")

            if hit_info.entity in invaders:
                reset_invader(hit_info.entity)

    # Check ammo collection
    for ammo_item in ammo:
        if not getattr(ammo_item, 'collected', False):
            ammo_item.y -= time.dt * ammo_item.dy
            if ammo_item.y <= -0.5:
                reset_ammo(ammo_item)

            if player.intersects(ammo_item).hit:
                ammo_item.collected = True
                ammo_item.y = -1
                bullet_count += 3
                bullet_count = min(bullet_count, max_bullets)
                invoke(reset_ammo, ammo_item, delay=0.5)

    # Increment score and update files
    current_time = time.time()
    if current_time - last_time >= 1:
        score += 12
        score_text.text = f"Score: {score}"
        last_time = current_time
        
        # Update player-specific score file
        if 'player_id' in globals():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                host = '0.tcp.in.ngrok.io'
                port = 12989
                sock.connect((host, port))
                score_data = f"{player_id}:{score}"
                sock.send(bytes(score_data, 'utf-8'))
                sock.close()
            except Exception as e:
                print(f"Error sending score: {e}")


def main():
    global controller, player_id, ws_client
    
    # Set fixed player_id instead of requesting one
    player_id = "player_1"  # This file will always be player 1
    print(f"Game started as {player_id}")
    
    # Initialize score file
    with open(f'scores_{player_id}.txt', 'w') as f:
        f.write('0')
    
    controller = HandGestureController()
    controller.start()
    
    # Initialize WebSocket client
    ws_client = WebSocketClient()
    ws_client.start()
    
    try:
        app.run()
    except Exception as e:
        print(f"Game error: {e}")
    finally:
        ws_client.stop()
        controller.stop()

def input(key):
    global current_lane, bullet_count

    if key == 'r' and game_over:  # Add restart on 'R' key press when game is over
        restart_game()
        return

    if game_over:
        return

    if key == "left arrow" and current_lane > 0:
        current_lane -= 1
        player.x = lanes[current_lane]

    elif key == "right arrow" and current_lane < 2:
        current_lane += 1
        player.x = lanes[current_lane]

    elif key == "space" and bullet_count > 0:
        Audio('assets/laser_sound.wav')
        bullet = Bullet()
        bullets.append(bullet)
        bullet_count -= 1


def reset_invader(invader):
    """Reset the position of an invader."""
    global locked_lane

    available_lanes = list(lanes)
    if locked_lane in available_lanes:
        available_lanes.remove(locked_lane)

    selected_lanes = sample(available_lanes, 2)  # Randomly pick 2 out of the 3 lanes
    invader.x = choice(selected_lanes)  # Place invader in one of the selected lanes
    invader.y = randint(80, 120) * 0.01

    locked_lane = list(set(lanes) - set(selected_lanes))[0]
    locked_until[locked_lane] = time.time() + randint(3, 5)  # Lock the lane for 3-5 seconds


def reset_ammo(ammo_item):
    """Reset the position of an ammo item."""
    ammo_item.x = choice(lanes)  # Place ammo in a random lane
    ammo_item.y = randint(80, 120) * 0.01  # Respawn at a random height
    ammo_item.collected = False  # Mark as active again


def end_game():
    """End the game and display the Game Over screen"""
    global game_over
    game_over = True

    # Display Game Over message and final score
    Text(text='Game Over', origin=(0, 0), scale=3, color=color.red, position=(0, 0.1), background=True, font=custom_font)
    Text(text=f'Final Score: {score}', origin=(0, 0), scale=2, color=color.yellow, position=(0, -0.1), background=True, font=custom_font)
    Text(text='Press R to Restart', origin=(0, 0), scale=2, color=color.green, position=(0, -0.3), background=True, font=custom_font)

    # Update score file with final score
    try:
        with open('scorekeeper.txt', 'r') as f:
            scores = {}
            for line in f:
                if ':' in line:
                    pid, pscore = line.strip().split(':')
                    scores[pid] = pscore
    except FileNotFoundError:
        scores = {}
    
    scores[player_id] = str(score)
    
    with open('scorekeeper.txt', 'w') as f:
        for pid, pscore in scores.items():
            f.write(f"{pid}:{pscore}\n")
    
    # Write final score to player-specific file
    with open(f'scores_{player_id}.txt', 'w') as f:
        f.write(str(score))
    
    # Send final score to server
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = '0.tcp.in.ngrok.io'
        port = 12989
        sock.connect((host, port))
        score_data = f"{player_id}:{score}"
        sock.send(bytes(score_data, 'utf-8'))
        sock.close()
    except Exception as e:
        print(f"Error updating final score: {e}")


class Invader(Entity):
    def __init__(self):
        super().__init__()
        self.parent = field
        self.model = 'quad'
        self.texture = 'alien.png'
        self.scale = 0.1
        self.position = (choice(lanes), randint(80, 120) * 0.01, -0.1)
        self.collider = 'box'
        self.dy = -0.15


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


class Ammo(Entity):
    def __init__(self):
        super().__init__()
        self.parent = field
        self.model = 'quad'
        self.texture = 'assets/ammo.png'  # Texture for the ammo
        self.scale = (0.05, 0.05, 0)
        self.position = (choice(lanes), randint(80, 120) * 0.01, -0.1)
        self.collider = 'box'
        self.dy = 0.15  # Speed at which the ammo moves downwards


app = Ursina()

custom_font = 'assets/Jersey15-Regular.ttf'  # Path to the custom font file

# Lane positions (left, middle, right)
lanes = [-0.5, 0, 0.5]
current_lane = 1  # Player starts in the middle lane
max_bullets = 5  # Maximum number of bullets player can have at once
bullet_count = max_bullets  # Player starts with a full clip

field_size = 19
Entity(model='quad', scale=60, texture='assets/dark_space_scene_variant')
field = Entity(model='quad', color=color.rgba(255, 255, 255, 0), scale=(12, 18),
               position=(field_size // 2, field_size // 2, -0.01))

bullets = []  # List to store bullets
invaders = []  # List to store invaders
ammo = []  # List to store ammo pickups
locked_lane = None  # The currently locked lane
locked_until = {lane: 0 for lane in lanes}  # Track when each lane is unlocked

player = Player()
player.x = lanes[current_lane]  # Position player in the middle

for i in range(5):  # Create 10 invaders
    invader = Invader()
    invaders.append(invader)

# Create ammo items randomly
for i in range(3):
    ammo_item = Ammo()
    ammo.append(ammo_item)

score = 0
last_time = time.time()
game_over = False

# Display score
score_text = Text(text='Score: 0', position=(-0.65, 0.4), origin=(0, 0), scale=2, color=color.violet, background=True, font=custom_font)

# Display ammo count
ammo_text = Text(text=f"Ammo: {bullet_count}", position=(0.65, 0.4), origin=(0, 0), scale=2, color=color.magenta, background=True, font=custom_font)

camera.position = (field_size // 2, -18, -18)
camera.rotation_x = -56

if __name__ == "__main__":
    if check_camera_permission():
        main()
    else:
        print("Please grant camera permission and restart the application")
