# Builtins
import threading
import argparse
import socket
import json
import time
import queue
# Relative
from game import *

player_positions = {}
position_lock = threading.Lock()
it_lock = threading.Lock()
clients = []
input_queue = queue.Queue()

it_player = None


def handle_client(conn, addr):
    global it_player
    player_id = addr[1]

    with position_lock:
        if it_player == None:
            it_player = player_id
        player_positions[player_id] = {"x": 0, "y": 0, "it": it_player == player_id }

    while True:
        try:
            data = conn.recv(1024).decode()
            if data:
                _input = {}
                for d in data.split('\n'):
                    if d:
                        _input.update(json.loads(d))
                input_queue.put((player_id, _input))  # Enqueue client input
                print("Received data from player:", player_id)
        except (ConnectionResetError, OSError):
            print(f"Closing player {player_id}'s connection")
            clients.remove(conn)
            conn.close()
            break
        finally:
            with position_lock:
                if player_positions.get(player_id):
                    print("Removing player", player_id)
                    del player_positions[player_id]
            with it_lock:
                if player_id == it_player:
                    it_player = None

def broadcast_positions(interval=0.03):
    while True:
        start_time = time.time()
        for conn in clients:
            try:
                position_data = json.dumps(player_positions).encode()
                position_data += b"\n"
                conn.sendall(position_data)
            except (BrokenPipeError, OSError):
                clients.remove(conn)
                conn.close()
        time.sleep(max(0, interval - (time.time() - start_time)))

def game_loop():
    global player_positions
    global it_player

    while True:
        # Process each client input
        print(input_queue.empty())
        while input_queue.not_empty:
            try:
                player_id, client_input = input_queue.get_nowait()
                print("Got input from player: ", player_id, client_input)
                with position_lock:
                    if client_input["action"] == "move":
                        if client_input["direction"] == "up":
                            player_positions[player_id]["y"] -= GameConfig.MAX_SPEED
                        elif client_input["direction"] == "down":
                            player_positions[player_id]["y"] += GameConfig.MAX_SPEED
                        elif client_input["direction"] == "left":
                            player_positions[player_id]["x"] -= GameConfig.MAX_SPEED
                        elif client_input["direction"] == "right":
                            player_positions[player_id]["x"] += GameConfig.MAX_SPEED
            except queue.Empty:
                pass

        with position_lock:
            for player_id, player in player_positions.items():
                # Process player input
                position = player_positions[it_player]
                if (
                    abs(player['x'] - position['x']) <=  GameConfig.COLLISION_DIST \
                        and abs(player['y'] - position['y']) <= GameConfig.COLLISION_DIST
                ):
                    with it_lock:
                        with position_lock:
                            it_player = player_id
                            position["it"] = False
                            player["it"] = True
        time.sleep(0.03)

def server_main(host, port):

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()

    threading.Thread(target=broadcast_positions, daemon=True).start()
    threading.Thread(target=game_loop, daemon=True).start()

    while True:
        conn, addr = server.accept()
        clients.append(conn)
        threading.Thread(target=handle_client, args=(conn, addr)).start()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default='127.0.0.1', type=str)
    parser.add_argument("--port", default=5555, type=int)
    args = parser.parse_args()

    server_main(args.host, args.port)