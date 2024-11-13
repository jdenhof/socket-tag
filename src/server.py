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
game_over = threading.Event()
it_lock = threading.Lock()
clients = []
input_queue = queue.Queue()

it_player = None


def handle_client(conn, addr):
    global it_player
    global player_positions
    player_id = addr[1]
    print(f"Handeling player connection {player_id}")

    with position_lock:
        if it_player == None:
            print(f"Player {player_id} is the first connection so by default is it")
            it_player = player_id
        player_positions[player_id] = {"x": 0, "y": 0, "it": it_player == player_id }

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
                if player_positions.get(player_id):
                    print("Removing player", player_id)
                    del player_positions[player_id]
            with it_lock:
                if player_id == it_player:
                    it_player = None

def broadcast_positions(interval=0.03):
    while not game_over.is_set():
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

def it_loop():
    global player_positions
    global it_player
    while not game_over.is_set():
        new_it_player = None
        with position_lock:
            with it_lock:
                it_player_pos = player_positions.get(it_player)
                if it_player_pos:
                    for player_id, player in player_positions.items():
                        if player_id == it_player:
                            continue
                        # Process player input
                        x_dist = abs(player['x'] - it_player_pos['x'])
                        y_dist = abs(player['y'] - it_player_pos['y'])
                        print(f"Distance from {it_player}->{player_id} x: {x_dist} y: {y_dist}")
                        if (x_dist <=  GameConfig.COLLISION_DIST and y_dist <= GameConfig.COLLISION_DIST):
                            new_it_player = player_id
                    if new_it_player:
                        it_player = new_it_player
                        it_player_pos["it"] = False
                        player_positions[it_player]["it"] = True

        time.sleep(GameConfig.TAG_DELAY if new_it_player else GameConfig.SERVER_SLEEP)

def movement_loop():
    global player_positions
    global it_player

    while not game_over.is_set():
        # Process each client input
        while input_queue.not_empty:
            try:
                player_id, client_input = input_queue.get_nowait()
                if player_positions.get(player_id) == None:
                    game_over.set()
                    raise RuntimeError(f"Attempting to modify player position for player {player_id} that doesn't exist\n\t{player_positions}")

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