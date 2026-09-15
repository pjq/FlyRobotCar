from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
FLY_DIR = Path(os.environ.get("FLY64_DIR", ROOT.parent / "fly")).resolve()
sys.path.insert(0, str(FLY_DIR))
from fly64.bridge import HEIGHT, WIDTH  # noqa: E402
from fly64.model import FlyModel  # noqa: E402

PORT, DT, MAX_SPEED = 8775, 0.02, 6.0
ROOM_HALF, CAR_RADIUS = 14.5, 0.72

# Authoritative furniture layout used by physics, fly vision and the browser.
OBJECTS = [
    {"kind": "sofa", "x": -7.0, "y": 5.0, "w": 5.0, "d": 2.0, "h": 1.6, "color": [47, 105, 155]},
    {"kind": "coffee table", "x": -3.8, "y": 1.3, "w": 3.0, "d": 1.8, "h": 0.8, "color": [137, 88, 49]},
    {"kind": "dining table", "x": 5.2, "y": 5.2, "w": 3.4, "d": 2.5, "h": 1.1, "color": [153, 103, 55]},
    {"kind": "bookshelf", "x": 10.8, "y": -4.2, "w": 1.4, "d": 5.0, "h": 3.2, "color": [101, 67, 43]},
    {"kind": "armchair", "x": -8.0, "y": -5.5, "w": 2.2, "d": 2.2, "h": 1.7, "color": [178, 83, 66]},
    {"kind": "plant", "x": 6.8, "y": -7.5, "w": 1.5, "d": 1.5, "h": 2.4, "color": [46, 135, 70]},
]


def wrap_angle(value: float) -> float:
    return (value + math.pi) % (2 * math.pi) - math.pi


def collides_object(x: float, y: float):
    for item in OBJECTS:
        if (abs(x - item["x"]) <= item["w"] / 2 + CAR_RADIUS and
                abs(y - item["y"]) <= item["d"] / 2 + CAR_RADIUS):
            return item
    return None


@dataclass
class AppliedControl:
    throttle: float
    steering: float


class World:
    def __init__(self):
        self.lock = threading.RLock()
        self.model = FlyModel(FLY_DIR / ".cache" / "malecns")
        self.frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
        self.paused = False
        self.avoidance_enabled = True
        self.reset()

    def reset(self):
        self.x, self.y, self.heading = 0.0, -9.5, math.pi / 2
        self.speed = self.distance = 0.0
        self.collisions = self.wall_collisions = 0
        self.last_collision_step = -100
        self.last_contact = "none"
        self.escape_ticks = 0
        self.escape_direction = 1.0
        self.last = {}

    def visual_threat(self, angle_offset: float) -> float:
        """Approximate a fly-like looming cue along one eye direction (0..1)."""
        angle = self.heading + angle_offset
        dx, dy = math.cos(angle), math.sin(angle)
        distances = []
        if abs(dx) > 1e-5:
            for boundary in (-ROOM_HALF, ROOM_HALF):
                d = (boundary - self.x) / dx
                if d > 0 and -ROOM_HALF <= self.y + dy*d <= ROOM_HALF: distances.append(d)
        if abs(dy) > 1e-5:
            for boundary in (-ROOM_HALF, ROOM_HALF):
                d = (boundary - self.y) / dy
                if d > 0 and -ROOM_HALF <= self.x + dx*d <= ROOM_HALF: distances.append(d)
        nearest = min(distances) if distances else 30.0
        for item in OBJECTS:
            rx, ry = item["x"] - self.x, item["y"] - self.y
            distance = math.hypot(rx, ry) - max(item["w"], item["d"]) / 2
            bearing = abs(wrap_angle(math.atan2(ry, rx) - angle))
            if bearing < .95: nearest = min(nearest, max(.1, distance))
        return max(0.0, min(1.0, (5.0 - nearest) / 4.0))

    def render_camera(self) -> tuple[np.ndarray, int]:
        """Render room walls, floor and furniture into a six-face camera atlas."""
        atlas = np.empty((HEIGHT, WIDTH, 3), np.uint8)
        face_angles = [0.0, math.pi / 2, math.pi, -math.pi / 2]
        visible = set()
        for face in range(6):
            image = np.empty((128, 128, 3), np.uint8)
            if face == 4: image[:] = [190, 198, 207]  # ceiling
            elif face == 5: image[:] = [112, 104, 94]  # floor
            else:
                horizon = 51
                image[:horizon] = [177, 187, 199]
                image[horizon:] = [112, 104, 94]
                angle = self.heading + face_angles[face]
                dx, dy = math.cos(angle), math.sin(angle)
                hits = []
                if abs(dx) > 1e-5:
                    for b in (-ROOM_HALF, ROOM_HALF):
                        dist = (b - self.x) / dx
                        if dist > 0 and -ROOM_HALF <= self.y + dy * dist <= ROOM_HALF: hits.append(dist)
                if abs(dy) > 1e-5:
                    for b in (-ROOM_HALF, ROOM_HALF):
                        dist = (b - self.y) / dy
                        if dist > 0 and -ROOM_HALF <= self.x + dx * dist <= ROOM_HALF: hits.append(dist)
                wall_distance = min(hits) if hits else 30
                top = max(2, int(horizon - 110 / max(wall_distance, 2)))
                image[top:106] = [132, 145, 160]
                image[104:108] = [63, 72, 82]
                # Project furniture into this 90-degree cube face.
                for n, item in enumerate(OBJECTS):
                    rx, ry = item["x"] - self.x, item["y"] - self.y
                    distance = math.hypot(rx, ry)
                    bearing = wrap_angle(math.atan2(ry, rx) - angle)
                    if distance < 22 and abs(bearing) < math.pi / 4:
                        visible.add(n)
                        center = int(64 + math.tan(bearing) * 64)
                        size = max(3, min(48, int(95 * max(item["w"], item["d"]) / (distance + 2))))
                        bottom = min(123, int(horizon + 72 / max(distance, 1.5)))
                        top_obj = max(5, bottom - int(size * item["h"] / 1.5))
                        left, right = max(0, center-size//2), min(128, center+size//2)
                        image[top_obj:bottom, left:right] = item["color"]
                # Floor tile perspective cues.
                for row in range(horizon + 8, 128, 14): image[row:row+1] = [87, 82, 77]
            atlas[(face // 3) * 128:(face // 3 + 1) * 128,
                  (face % 3) * 128:(face % 3 + 1) * 128] = image
        return atlas, len(visible)

    def tick(self):
        with self.lock:
            if self.paused: return
            self.frame, visible_objects = self.render_camera()
            brain, spikes = self.model.step(self.frame, self.model.step_count * self.model.dt)
            raw_throttle = max(0.0, brain.y / 70.0)
            raw_steering = max(-1.0, min(1.0, brain.x / 70.0))
            left_threat, right_threat = self.visual_threat(.48), self.visual_threat(-.48)
            threat = max(left_threat, right_threat)
            control = AppliedControl(raw_throttle, raw_steering)
            source = "MaleCNS"
            if self.avoidance_enabled and self.escape_ticks > 0:
                control = AppliedControl(.24, self.escape_direction * .9)
                source = "tactile escape reflex"
                self.escape_ticks -= 1
            elif self.avoidance_enabled and threat > .18:
                # A looming object in the left eye turns the vehicle right, and
                # vice versa. Keep a little motion so steering can take effect.
                avoidance_turn = max(-1.0, min(1.0, (right_threat - left_threat) * 1.7))
                if abs(avoidance_turn) < .18:
                    avoidance_turn = .65 if raw_steering >= 0 else -.65
                control = AppliedControl(max(.22, min(raw_throttle, .38)), avoidance_turn)
                source = "visual avoidance reflex"
            target_speed = control.throttle * MAX_SPEED
            self.speed += (target_speed - self.speed) * .12
            if self.speed < .08: self.speed = 0.0
            turn_rate = self.speed * .34
            if source == "tactile escape reflex":
                turn_rate = max(turn_rate, 1.35)  # differential-drive pivot at contact
            self.heading = wrap_angle(self.heading + control.steering * turn_rate * DT)
            nx = self.x + math.cos(self.heading) * self.speed * DT
            ny = self.y + math.sin(self.heading) * self.speed * DT

            contact = None
            if abs(nx) + CAR_RADIUS >= ROOM_HALF or abs(ny) + CAR_RADIUS >= ROOM_HALF:
                contact = "room wall"; self.wall_collisions += self.model.step_count - self.last_collision_step >= 50
            else:
                item = collides_object(nx, ny)
                if item: contact = item["kind"]

            if contact:
                if self.model.step_count - self.last_collision_step >= 50:
                    self.collisions += 1; self.last_collision_step = self.model.step_count
                if self.avoidance_enabled and self.escape_ticks == 0:
                    self.escape_ticks = 120
                    self.escape_direction = -1.0 if left_threat >= right_threat else 1.0
                self.speed = 0.0
                self.last_contact = contact
            else:
                self.x, self.y = nx, ny
                self.distance += self.speed * DT
                self.last_contact = "none"
                if source == "tactile escape reflex":
                    self.escape_ticks = 0

            self.last = {
                "x": round(self.x, 3), "y": round(self.y, 3), "heading": round(self.heading, 4),
                "speed": round(self.speed, 2), "raw_throttle": brain.y, "raw_steering": brain.x,
                "throttle": round(control.throttle * 70), "steering": round(control.steering * 70),
                "control_source": source, "avoidance_enabled": self.avoidance_enabled,
                "left_threat": round(left_threat, 2), "right_threat": round(right_threat, 2),
                "assist": source != "MaleCNS", "safe_mode": False,
                "distance": round(self.distance, 2), "collisions": self.collisions,
                "wall_collisions": self.wall_collisions, "last_contact": self.last_contact,
                "visible_objects": visible_objects, "object_count": len(OBJECTS),
                "spikes": int(len(spikes)), "step": self.model.step_count, "paused": self.paused,
                "neurons": self.model.n, "edges": int(self.model.w.nnz),
            }

    def state(self):
        with self.lock: return dict(self.last)


WORLD = World()


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, body: bytes, kind: str):
        self.send_response(200); self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/state": return self.send_bytes(json.dumps(WORLD.state()).encode(), "application/json")
        if self.path == "/vision":
            with WORLD.lock: body = WORLD.model.retina.preview(WORLD.frame).tobytes()
            return self.send_bytes(body, "application/octet-stream")
        if self.path == "/objects": return self.send_bytes(json.dumps(OBJECTS).encode(), "application/json")
        return self.send_bytes((ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        with WORLD.lock:
            if self.path == "/reset": WORLD.reset()
            elif self.path == "/pause": WORLD.paused = not WORLD.paused
            elif self.path == "/avoidance": WORLD.avoidance_enabled = not WORLD.avoidance_enabled
            else: self.send_response(404); self.end_headers(); return
        self.send_response(204); self.end_headers()

    def log_message(self, *_): pass


def loop():
    deadline = time.monotonic()
    while True:
        WORLD.tick(); deadline += DT
        time.sleep(max(0, deadline - time.monotonic()))
        if time.monotonic() - deadline > DT: deadline = time.monotonic()


if __name__ == "__main__":
    threading.Thread(target=loop, daemon=True).start()
    print(f"FlyRobotCar: http://127.0.0.1:{PORT}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
