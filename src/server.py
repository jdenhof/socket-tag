# server.py
import threading
import queue
import socket
import json
import time
import argparse

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
                    for addr in self.clients:
                        self.sock.sendto(data, addr)
            time.sleep(game.GameConfig.SERVER_SLEEP)
        self.stop("No longer broadcasting game state!")

    def receive_inputs(self):
        while not self.game_state.game_over:
            data, addr = self.sock.recvfrom(self.buffer_size)
            with self._client_lock:
                if addr not in self.clients:
                    print("New player connected:", addr)
                    self.clients.add(addr)
            self.input_queue.put((addr, data))
        self.stop("No longer receiving inputs!")

    def process_inputs(self):
        while not self.game_state.game_over:
            addr, data = self.input_queue.get()
            cmd = json.loads(data.decode())
            self.game_state.handle_player_input(str(addr), cmd)
        self.stop("No longer processing inputs!")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default='0.0.0.0', type=str)
    parser.add_argument("--port", default=5555, type=int)
    args = parser.parse_args()

    server = GameServer(args.host, args.port)
    server.start()