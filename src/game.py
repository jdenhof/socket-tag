# game.py
from dataclasses import dataclass
import threading
import time
import math

DEBUG = False

class GameConfig:
    PLAYER_SPEED = 10
    MAX_SPEED = 100
    PLAYER_SIZE = 20
    TAG_DELAY = 3
    SERVER_SLEEP = .0166
    FRICTION = 100
    WINDOW_WIDTH = 800
    WINDOW_HEIGHT = 800
    TAGGED_MAX_SPEED = 150

class Colors:
    WHITE = (255, 255, 255)
    BLUE = (0, 0, 255)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)

@dataclass
class Player:
    id: int
    x: int = 0
    y: int = 0
    vx: int = 0
    vy: int = 0

class GameState:

    def __init__(self):
        self._lock = threading.Lock()
        self._can_tag = threading.Event()
        self._game_over = threading.Event()
        self._can_tag.set()
        self.players = {}
        self.tagged = None
        self.last_update_time = time.time()

    @property
    def game_over(self):
        return self._game_over.is_set()

    @game_over.setter
    def game_over(self, value):
        if value == True:
            self._game_over.set()
        elif value == False:
            self._game_over.clear()
        else:
            raise RuntimeError(f"Unsupported game_over value {value}!")

    def remove_player(self, player_id):
        with self._lock:
            if player_id not in self:
                raise RuntimeError("Attempting to remove uninitialized player!")
            del self[player_id]

    def handle_player_input(self, player_id, cmd):
        if DEBUG:
            print(f"Received command from {player_id}: {cmd}")
        max_speed = GameConfig.TAGGED_MAX_SPEED if player_id == self.tagged else GameConfig.MAX_SPEED
        with self._lock:
            if "type" not in cmd:
                raise RuntimeError("Invalid command! No type available")
            elif cmd["type"] == "join":
                self.players[player_id] = {
                    "x": GameConfig.WINDOW_WIDTH // 2,
                    "y": GameConfig.WINDOW_HEIGHT // 2,
                    "vx": 0,
                    "vy": 0
                }
                if len(self.players) == 1:
                    self.tag_player(player_id)

            elif cmd["type"] == "move":
                player = self.players.get(player_id)
                if not player:
                    raise RuntimeError("Player sent command without requesting to join!")
                if "direction" not in cmd:
                    raise RuntimeError("Player requested cmd 'action' without 'direction'")

                if "up" in cmd["direction"]:
                    player["vy"] = max(
                        -max_speed, player["vy"] - GameConfig.PLAYER_SPEED
                    )
                if "down" in cmd["direction"]:
                    player["vy"] = min(
                        max_speed, player["vy"] + GameConfig.PLAYER_SPEED
                    )
                if "left" in cmd["direction"]:
                    player["vx"] = max(
                        -max_speed, player["vx"] - GameConfig.PLAYER_SPEED
                    )
                if "right" in cmd["direction"]:
                    player["vx"] = min(
                        max_speed, player["vx"] + GameConfig.PLAYER_SPEED
                    )
            else:
                raise RuntimeError(f"Invalid command type '{cmd['type']}'")

    def game_tick(self):
        with self._lock:
            current_time = time.time()
            delta_time = current_time - self.last_update_time
            self.last_update_time = current_time

            # Update player positions based on velocity and delta time
            for player_id, config in self.players.items():
                config["x"] += config["vx"] * delta_time
                config["y"] += config["vy"] * delta_time

                # Keep players within bounds
                config["x"] = max(
                    GameConfig.PLAYER_SIZE,
                    min(GameConfig.WINDOW_WIDTH - GameConfig.PLAYER_SIZE, config["x"])
                )
                config["y"] = max(
                    GameConfig.PLAYER_SIZE,
                    min(GameConfig.WINDOW_HEIGHT - GameConfig.PLAYER_SIZE, config["y"])
                )

                # Apply friction scaled by delta time
                if config["vx"] > 0:
                    config["vx"] = max(0, config["vx"] - GameConfig.FRICTION * delta_time)
                elif config["vx"] < 0:
                    config["vx"] = min(0, config["vx"] + GameConfig.FRICTION * delta_time)

                if config["vy"] > 0:
                    config["vy"] = max(0, config["vy"] - GameConfig.FRICTION * delta_time)
                elif config["vy"] < 0:
                    config["vy"] = min(0, config["vy"] + GameConfig.FRICTION * delta_time)

            # Perform tagging logic
            if self.tagged is not None and self._can_tag.is_set():
                candidates = []
                it_pos = self.players[self.tagged]
                for player_id, config in self.players.items():
                    if player_id == self.tagged:
                        continue

                    distance = (config["x"] - it_pos["x"])**2 + (config["y"] - it_pos["y"])**2
                    # if math.sqrt(abs(config["x"] - it_pos["x"])**2 + abs(config["y"] - it_pos["y"])**2) == GameConfig.PLAYER_SIZE:
                    if math.sqrt(distance) <= GameConfig.PLAYER_SIZE*2:
                    # if abs(config["x"] - it_pos["x"]) <= GameConfig.PLAYER_SIZE*2 and abs(
                    #     config["y"] - it_pos["y"]
                    # ) <= GameConfig.PLAYER_SIZE*2:
                        # distance = (config["x"] - it_pos["x"])**2 + (config["y"] - it_pos["y"])**2
                        candidates.append((distance, player_id))

                if candidates:
                    _, tagged_player = min(candidates)
                    self.tag_player(tagged_player)

    def tag_player(self, player_id):
        """Tags a player and enforces a delay before tagging can happen again."""
        if not self._can_tag.is_set():
            return  # Skip tagging if delay is active

        self.tagged = player_id

        # Disable tagging and start the delay timer
        self._can_tag.clear()
        threading.Thread(target=self._tag_cooldown, daemon=True).start()

    def _tag_cooldown(self):
        """Cooldown period during which tagging is disabled."""
        time.sleep(GameConfig.TAG_DELAY)
        self._can_tag.set()

    def get_game_state(self):
        """Return the current game state."""
        with self._lock:
            return {
                "type": "update",
                "tagged": {
                    "id": self.tagged,
                    "delay": not self._can_tag.is_set()
                },
                "players": self.players
            }
