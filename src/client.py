# client.py
import threading
import queue
import json
import socket
import sys
import argparse

import pygame

from game import *

class GameClient:

    def __init__(self, host, port, buffer_size=1024):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self._lock = threading.Lock()
        self.game_started = threading.Event()
        self.input_queue = queue.Queue()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', self.port))
        self.game_state = None
        self.joined = threading.Event()

    def join_game(self):
        join_request = {"type": "join"}
        self.sock.sendto(json.dumps(join_request).encode(), (self.host, self.port))
        self.joined.set()

    def game_loop(self):
        print("Starting Game Loop")
        pygame.init()

        # Screen settings
        width, height = GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT
        screen = pygame.display.set_mode((width, height))

        pygame.display.set_caption("Tag")

        # Main loop
        running = True
        while running:
            if self.game_state is None:
                continue
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
                command = { "type": "move", "direction": [] }
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
                    self.input_queue.put(command)

            with self._lock:
                for name, p in self.game_state["players"].items():
                    color = Colors.BLUE
                    if self.game_state["tagged"]["id"] == name:
                        if self.game_state["tagged"]["delay"]:
                            color = Colors.GREEN
                        else:
                            color = Colors.RED

                    pygame.draw.circle(screen, color, (p['x'], p['y']), GameConfig.PLAYER_SIZE)

            # Update the display
            pygame.display.flip()
            # Frame rate
            pygame.time.Clock().tick(30)

    def broadcast_commands(self):
        while True:
            command = self.input_queue.get()
            try:
                self.sock.sendto(command.encode(), (self.host, self.port))
            except (BrokenPipeError, OSError) as e:
                print("Error sending data:", e)
                break

    def receive_game_state(self):
        #self.sock.bind((self.host, self.port+1))
        #self.sock.bind(('', 0))
        self.joined.wait()
        while True:
            data, _ = self.sock.recvfrom(self.buffer_size)

            if data:
                data = data.decode()
                with self._lock:
                    self.game_state = json.loads(data)

    def start(self):

        threading.Thread(target=self.broadcast_commands, daemon=True).start()
        threading.Thread(target=self.receive_game_state, daemon=True).start()

        self.join_game()
        self.game_loop()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default='127.0.0.1', type=str)
    parser.add_argument("--port", default=5555, type=int)
    args = parser.parse_args()

    client = GameClient(args.host, args.port)
    client.start()