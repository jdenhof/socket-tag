# Builtins
import sys
import threading
import argparse
import socket
import json
import time
import queue
# Relative
from game import *

player_configs = {}
position_lock = threading.Lock()
game_over = threading.Event()
can_tag = threading.Event()
input_queue = queue.Queue()
it_lock = threading.Lock()
clients = []

it_player = None

def register_new_player(player_id):
    global player_configs

    if player_id in player_configs:
        sys.stderr.write(f"Attempting to register player {player_id} who has already been registered")
        return

    with position_lock:
        player_configs[player_id] = {
            "x": 0,
            "y": 0,
            "it": False,
            "vx": 0,
            "vy": 0
        }

    with it_lock:
        if it_player is None:
            player_tagged(player_id)


def handle_client(conn, addr):
    global it_player
    global player_configs
    player_id = addr[1]

    sys.stderr.write(f"Handeling player connection {player_id}")
    register_new_player(player_id)

    while not game_over.is_set():
        try:
            data = conn.recv(1024).decode()
            if data:
                _input = {}
                for d in data.split('\n'):
                    if d:
                        _input.update(json.loads(d))
                input_queue.put((player_id, _input))  # Enqueue client input
        except (ConnectionResetError, OSError):
            print(f"Closing player {player_id}'s connection")

            clients.remove(conn)
            conn.close()

            with position_lock:
                if player_configs.get(player_id):
                    print("Removing player", player_id)
                    del player_configs[player_id]
            with it_lock:
                if player_id == it_player:
                    it_player = None

def broadcast_positions(interval=0.03):
    while not game_over.is_set():
        start_time = time.time()

        with position_lock:
            for config in player_configs.values():

                config["x"] += config["vx"]
                config["y"] += config["vy"]

                if config["vy"] > 0:
                    config["vy"] = max(0, config["vy"] - GameConfig.FRICTION)
                if config["vy"] < 0:
                    config["vy"] = min(0, config["vy"] + GameConfig.FRICTION)

                if config["vx"] > 0:
                    config["vx"] = max(0, config["vx"] - GameConfig.FRICTION)
                if config["vx"] < 0:
                    config["vx"] = min(0, config["vx"] + GameConfig.FRICTION)

        for conn in clients:
            try:
                print(player_configs)
                position_data = json.dumps(player_configs).encode()
                position_data += b"\n"
                conn.sendall(position_data)
            except (BrokenPipeError, OSError):
                clients.remove(conn)
                conn.close()
        time.sleep(max(0, interval - (time.time() - start_time)))

def player_tagged(player_id):
    threading.Thread(target=player_tagged_thread, args=(player_id,)).start()

def player_tagged_thread(player_id):
    global player_configs
    global it_player

    can_tag.clear()

    current_it_player = it_player

    with it_lock:
        it_player = player_id

    with position_lock:
        if current_it_player:
            player_configs[current_it_player]["it"] = False
        player_configs[player_id]["it"] = True
        player_configs[player_id]["it_delay"] = True

    time.sleep(GameConfig.TAG_DELAY)

    with position_lock:
        del player_configs[player_id]["it_delay"]

    can_tag.set()

def it_loop():
    global player_configs
    global it_player
    can_tag.set()

    while not game_over.is_set():
        can_tag.wait()
        with position_lock, it_lock:
            it_player_pos = player_configs.get(it_player)
            if it_player_pos:
                for player_id, player in player_configs.items():
                    if player_id == it_player:
                        continue
                    # Process player input
                    x_dist = abs(player['x'] - it_player_pos['x'])
                    y_dist = abs(player['y'] - it_player_pos['y'])
                    if (x_dist <=  GameConfig.COLLISION_DIST and y_dist <= GameConfig.COLLISION_DIST):
                        player_tagged(player_id)
                        break

        time.sleep(GameConfig.SERVER_SLEEP)

def movement_loop():
    global player_configs
    global it_player

    while not game_over.is_set():
        # Process each client input
        while input_queue.not_empty:
            try:
                player_id, client_input = input_queue.get_nowait()
                if player_configs.get(player_id) == None:
                    game_over.set()
                    raise RuntimeError(f"Attempting to modify player position for player {player_id} that doesn't exist\n\t{player_configs}")

                with position_lock:
                    if client_input["action"] == "move":
                        if "up" in client_input["direction"]:
                            if abs(player_configs[player_id]["vy"]) < GameConfig.MAX_SPEED:
                                player_configs[player_id]["vy"] -= GameConfig.PLAYER_SPEED
                        if "down" in client_input["direction"]:
                            if abs(player_configs[player_id]["vy"]) < GameConfig.MAX_SPEED:
                                player_configs[player_id]["vy"] += GameConfig.PLAYER_SPEED
                        if "left" in client_input["direction"]:
                            if abs(player_configs[player_id]["vx"]) < GameConfig.MAX_SPEED:
                                player_configs[player_id]["vx"] -= GameConfig.PLAYER_SPEED
                        if "right" in client_input["direction"]:
                            if abs(player_configs[player_id]["vx"]) < GameConfig.MAX_SPEED:
                                player_configs[player_id]["vx"] += GameConfig.PLAYER_SPEED
            except queue.Empty:
                pass

def server_main(host, port):

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()

    threading.Thread(target=broadcast_positions, daemon=True).start()
    threading.Thread(target=movement_loop, daemon=True).start()
    threading.Thread(target=it_loop, daemon=True).start()

    while not game_over.is_set():
        conn, addr = server.accept()
        clients.append(conn)
        threading.Thread(target=handle_client, args=(conn, addr)).start()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default='127.0.0.1', type=str)
    parser.add_argument("--port", default=5555, type=int)
    args = parser.parse_args()

    server_main(args.host, args.port)