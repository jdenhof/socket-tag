import threading
import queue
import json
import socket
import sys
import argparse

import pygame

from game import *

# Queue to hold player inputs to be sent to the server
input_queue = queue.Queue()
position_lock = threading.Lock()
player_positions = {}

# Initialize Pygame
def game():
    print("Starting Game Loop")
    pygame.init()

    # Screen settings
    width, height = 400, 400
    screen = pygame.display.set_mode((width, height))

    pygame.display.set_caption("Tag")

    # Main loop
    running = True
    while running:
        # Fill the background
        screen.fill(Colors.WHITE)
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        command = None
        # Get keys pressed
        keys = pygame.key.get_pressed()
        if keys.count(True) >= 1:
            command = { "action": "move", "direction": [] }
            # Movement based on key presses
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                command["direction"].append("up")
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                command["direction"].append("down")
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                command["direction"].append("left")
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                command["direction"].append("right")

            if command:
                command = json.dumps(command)
                input_queue.put(command)

        with position_lock:
            for name, p in player_positions.items():
                color = Colors.BLUE
                if p["it"]:
                    color = Colors.RED
                if p.get("it_delay"):
                    color = Colors.GREEN

                pygame.draw.circle(screen, color, (p['x'], p['y']), GameConfig.PLAYER_SIZE)

        # Update the display
        pygame.display.flip()
        # Frame rate
        pygame.time.Clock().tick(30)

# Function to send data to the server continuously
def send_data(sock):
    while True:

        if not input_queue.empty():
            try:
                command = input_queue.get_nowait()
            except queue.Empty:
                continue
            try:
                sock.sendall(command.encode() + b"\n")
            except (BrokenPipeError, OSError) as e:
                print("Error sending data:", e)
                break

# Function to receive data from the server continuously
def receive_data(sock):
    global player_positions
    while True:
        try:
            data = sock.recv(1024).decode()
            if data:
                with position_lock:
                    data = data.split('\n')[-2]
                    player_positions = json.loads(data)
        except (ConnectionResetError, OSError) as e:
            print("Error receiving data:", e)
            break

def client_main(host, port):

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    threading.Thread(target=send_data, args=(sock,), daemon=True).start()
    threading.Thread(target=receive_data, args=(sock,), daemon=True).start()

    game()

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default='127.0.0.1', type=str)
    parser.add_argument("--port", default=5555, type=int)
    args = parser.parse_args()

    client_main(args.host, args.port)