# server.py
import threading
import queue
import socket
import json
import time

import game


class GameServer:
    def __init__(self, host, port, buffer_size=1024):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.input_queue = queue.Queue()
        self.game_state = game.GameState()
        self._client_lock = threading.Lock()
        self.clients = set()

    def start(self):

        self.sock.bind((self.host, self.port))
        print(f"Socket bound to {self.host}:{self.port}")

        threading.Thread(target=self.broadcast_game_state, daemon=True).start()
        threading.Thread(target=self.receive_inputs, daemon=True).start()
        threading.Thread(target=self.process_inputs, daemon=True).start()

        while not self.game_state.game_over:
            try:
                self.game_state.game_tick()
            except KeyboardInterrupt:
                self.stop("\nServer killed!")

    def stop(self, reason=""):
        if reason:
            print(reason)
        self.game_state.game_over = True

    def broadcast_game_state(self):
        while not self.game_state.game_over:
            with self._client_lock:
                if self.clients:
                    state = self.game_state.get_game_state()
                    data = json.dumps(state).encode()
                    for port in self.clients:
                        self.sock.sendto(data, (self.host, port))
            time.sleep(game.GameConfig.SERVER_SLEEP)
        self.stop("No longer broadcasting game state!")

    def receive_inputs(self):
        while not self.game_state.game_over:
            data, (_, port) = self.sock.recvfrom(self.buffer_size)
            with self._client_lock:
                if port not in self.clients:
                    self.clients.add(port)
            self.input_queue.put((str(port), data))
        self.stop("No longer receiving inputs!")

    def process_inputs(self):
        while not self.game_state.game_over:
            player_id, data = self.input_queue.get()
            cmd = json.loads(data.decode())
            self.game_state.handle_player_input(player_id, cmd)
        self.stop("No longer processing inputs!")


if __name__ == "__main__":

    server = GameServer("0.0.0.0", 5555)
    server.start()