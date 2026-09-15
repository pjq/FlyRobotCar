from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path

import numpy as np
import pyarrow.feather as feather

ROOT = Path(__file__).resolve().parent
FLY_DIR = Path(os.environ.get("FLY64_DIR", ROOT.parent / "fly")).resolve()
sys.path.insert(0, str(FLY_DIR))
from fly64.bridge import HEIGHT, WIDTH  # noqa: E402
from fly64.model import FlyModel  # noqa: E402

PORT, DT, MAX_SPEED = 8775, 0.02, 8.0
# Large room: world spans 48 x 48 units, leaving space for free exploration.
ROOM_HALF, ROOM_HEIGHT, CAR_RADIUS = 24.0, 7.0, 0.72
MAX_FLIGHT_Z = ROOM_HEIGHT - 1.2

# Authoritative furniture layout used by physics, fly vision and the browser.
OBJECTS = [
    {"kind": "sofa", "x": -7.0, "y": 5.0, "w": 5.0, "d": 2.0, "h": 1.6, "color": [47, 105, 155]},
    {"kind": "coffee table", "x": -3.8, "y": 1.3, "w": 3.0, "d": 1.8, "h": 0.8, "color": [137, 88, 49]},
    {"kind": "dining table", "x": 5.2, "y": 5.2, "w": 3.4, "d": 2.5, "h": 1.1, "color": [153, 103, 55]},
    {"kind": "bookshelf", "x": 10.8, "y": -4.2, "w": 1.4, "d": 5.0, "h": 3.2, "color": [101, 67, 43]},
    {"kind": "armchair", "x": -8.0, "y": -5.5, "w": 2.2, "d": 2.2, "h": 1.7, "color": [178, 83, 66]},
    {"kind": "plant", "x": 6.8, "y": -7.5, "w": 1.5, "d": 1.5, "h": 2.4, "color": [46, 135, 70]},
 ]

# Box Road: orthogonal route only—horizontal and vertical segments, no diagonals.
Z_SEGMENTS = [((-10.0, -18.0), (10.0, -18.0)),
              ((10.0, -18.0), (10.0, -10.0)),
              ((10.0, -10.0), (-10.0, -10.0)),
              ((-10.0, -10.0), (-10.0, -2.0)),
              ((-10.0, -2.0), (10.0, -2.0)),
              ((10.0, -2.0), (10.0, 6.0)),
              ((10.0, 6.0), (-10.0, 6.0)),
              ((-10.0, 6.0), (-10.0, 14.0)),
              ((-10.0, 14.0), (0.0, 14.0))]
for (ax, ay), (bx, by) in Z_SEGMENTS:
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    for distance in np.arange(0.0, length + 0.1, 2.0):
        t = distance / length
        cx, cy = ax + dx * t, ay + dy * t
        for side in (-1.0, 1.0):
            OBJECTS.append({"kind": "box", "x": cx + side * nx * 3.4,
                            "y": cy + side * ny * 3.4, "w": 1.5, "d": 1.5,
                            "h": 2.0, "color": [43, 112, 185]})


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
        self.neuron_groups = self._load_neuron_groups()
        self.frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
        self.paused = False
        self.flight_enabled = True
        self.neural_escape_enabled = True
        self.stimulus_ticks = {}
        self.events = []
        self.reset()

    def reset(self):
        self.x, self.y, self.heading = -10.0, -18.0, 0.0
        self.z = self.vertical_speed = 0.0
        self.flying = False
        self.ceiling_contacts = 0
        self.flight_candidate_ticks = 0
        self.neural_loom_memory = 0.0
        self.neural_escape_memory = 0.0
        self.neural_flight_memory = 0.0
        self.auto_takeoffs = 0
        self.speed = self.distance = 0.0
        self.collisions = self.wall_collisions = 0
        self.box_successes = 0
        self.last_collision_step = -100
        self.last_contact = "none"
        self.escape_ticks = 0
        self.escape_direction = 1.0
        self.stimulus_ticks.clear()
        self.events = []
        self.throttle_history = deque(maxlen=8)
        self.steering_history = deque(maxlen=8)
        self.last = {}

    def _load_neuron_groups(self):
        """Resolve named biological cell types to prepared model indices."""
        cache = FLY_DIR / ".cache" / "malecns"
        ids = np.load(cache / "model.npz", allow_pickle=False)["ids"]
        table = feather.read_table(cache / "raw" / "annotations.feather", columns=["bodyId", "flywireType", "type", "instance", "somaSide"]).to_pandas()
        labels = table["flywireType"].fillna(table["type"]).astype(str)
        index = {int(body): i for i, body in enumerate(ids)}
        groups = {}
        for name in ("LC4", "LPLC2", "DNp01", "DNp10", "DNp02", "DNp04", "DNp11", "DNg100", "DNa02", "DNg13"):
            selected = table.loc[labels.eq(name)].copy()
            bodies = selected["bodyId"].astype(int)
            groups[name] = np.asarray([index[b] for b in bodies if b in index], dtype=np.int32)
            instances = selected["instance"].fillna("").astype(str).str.upper()
            sides = selected["somaSide"].fillna("").astype(str).str.upper()
            groups[f"{name}_L"] = np.asarray([index[b] for b, side, inst in zip(bodies, sides, instances)
                                                   if b in index and (side == "L" or "_L" in inst)], dtype=np.int32)
            groups[f"{name}_R"] = np.asarray([index[b] for b, side, inst in zip(bodies, sides, instances)
                                                   if b in index and (side == "R" or "_R" in inst)], dtype=np.int32)
        return groups

    def group_rate(self, name: str, spikes: np.ndarray) -> float:
        group = self.neuron_groups[name]
        return float(np.isin(group, spikes).sum() / max(len(group), 1) / DT)

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
            # Interactive, explicitly labeled optogenetic-style test pulse.
            for name, ticks in list(self.stimulus_ticks.items()):
                if ticks > 0:
                    self.model.v[self.neuron_groups[name]] += 1.25
                    self.stimulus_ticks[name] = ticks - 1
                else:
                    del self.stimulus_ticks[name]
            brain, spikes = self.model.step(self.frame, self.model.step_count * self.model.dt)
            # Motor readout follows the named MaleCNS populations. The
            # model's generic output is retained for comparison, but the car
            # command is derived from DNg100 and bilateral DNa02/DNg13 rates.
            dng_rate = self.group_rate("DNg100", spikes)
            left_turn = self.group_rate("DNa02_L", spikes) + self.group_rate("DNg13_L", spikes)
            right_turn = self.group_rate("DNa02_R", spikes) + self.group_rate("DNg13_R", spikes)
            # Named motor populations are tiny (often two cells), so use a
            # short causal rate window. This removes single-step 0/25/50 Hz
            # jitter while keeping the command entirely neuron-derived.
            # FlyModel's rolling readout is already built from the annotated
            # DNg100 and bilateral DNa02/DNg13 pools; use it as the stable
            # named-population motor signal rather than a one-tick spike.
            self.throttle_history.append(max(0.0, min(1.0, brain.y / 70.0)))
            self.steering_history.append(max(-1.0, min(1.0, brain.x / 70.0)))
            raw_throttle = max(0.0, min(1.0, float(np.mean(self.throttle_history))))
            raw_steering = max(-1.0, min(1.0, float(np.mean(self.steering_history))))
            # Neural-only escape experiment: geometry is not consulted for
            # steering. We only read the named MaleCNS populations after the
            # complete network has propagated the visual input.
            lc4_rate = self.group_rate("LC4", spikes)
            lplc2_rate = self.group_rate("LPLC2", spikes)
            dnp01_rate = self.group_rate("DNp01", spikes)
            dnp10_rate = self.group_rate("DNp10", spikes)
            dnp_rate = dnp01_rate + dnp10_rate
            flight_rate = (self.group_rate("DNp02", spikes) + self.group_rate("DNp04", spikes) + self.group_rate("DNp11", spikes))
            # Short causal memories model neural persistence at 50 Hz; this
            # avoids requiring three tiny populations to spike on one exact tick.
            self.neural_loom_memory = .92 * self.neural_loom_memory + .08 * (lc4_rate + lplc2_rate)
            self.neural_escape_memory = .92 * self.neural_escape_memory + .08 * dnp_rate
            self.neural_flight_memory = .92 * self.neural_flight_memory + .08 * flight_rate
            dna_rate = left_turn + right_turn
            control = AppliedControl(raw_throttle, raw_steering)
            source = "MaleCNS"
            # Automatic takeoff: the Flight Test button only injects a
            # stimulus; normal flight must come from the neural pathway.
            looming_rate = lc4_rate + lplc2_rate
            if not self.flying and self.neural_loom_memory > 4.0 and self.neural_escape_memory > 2.0 and self.neural_flight_memory > 2.0:
                self.flight_candidate_ticks += 1
            else:
                self.flight_candidate_ticks = max(0, self.flight_candidate_ticks - 1)
            if self.flight_enabled and not self.flying and self.flight_candidate_ticks >= 3:
                self.flying = True
                self.z = max(self.z, .3)
                self.auto_takeoffs += 1
                self.flight_candidate_ticks = 0
                source = "MaleCNS neural takeoff"
            if self.neural_escape_enabled and self.escape_ticks > 0:
                control = AppliedControl(.30, self.escape_direction)
                source = "MaleCNS tactile escape"
                self.escape_ticks -= 1
            elif self.neural_escape_enabled and (lc4_rate + lplc2_rate) > 8.0 and dnp_rate > 8.0:
                # The escape command comes from DNp01/DNp10. Direction comes
                # only from the neural steering readout, never room coordinates.
                control = AppliedControl(raw_throttle * .45, raw_steering)
                source = "MaleCNS neural escape"
            target_speed = control.throttle * MAX_SPEED
            if self.flying:
                # Modeled flight dynamics; neural groups choose takeoff and
                # flight drive, while gravity/drag are explicit physics.
                lift = max(-1.0, min(1.0, self.neural_flight_memory / 10.0 - .2))
                self.vertical_speed += (lift * 5.0 - 2.4) * DT
                self.vertical_speed *= .985
                self.z += self.vertical_speed * DT
                if self.z >= MAX_FLIGHT_Z:
                    self.z = MAX_FLIGHT_Z
                    self.vertical_speed = -1.0
                    self.ceiling_contacts += 1
                if self.z <= 0.0:
                    self.z = 0.0
                    self.vertical_speed = 0.0
                    self.flying = False
            self.speed += (target_speed - self.speed) * .12
            if self.speed < .08: self.speed = 0.0
            turn_rate = self.speed * .34
            if source == "MaleCNS tactile escape":
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
                self.speed = 0.0
                if self.neural_escape_enabled and self.escape_ticks == 0:
                    # Contact is represented as a short tactile escape phase.
                    # Direction comes from the neural steering readout, not
                    # from the furniture coordinates.
                    self.escape_ticks = 80
                    self.escape_direction = -1.0 if raw_steering >= 0 else 1.0
                self.last_contact = contact
            else:
                previous_y = self.y
                self.x, self.y = nx, ny
                self.distance += self.speed * DT
                self.last_contact = "none"
                # Evaluation only: crossing the marked Box Road finish line
                # counts success; it never changes steering or throttle.
                if self.x > -0.5 and self.y > 13.5:
                    self.box_successes += 1
                    self.x, self.y, self.heading = -10.0, -18.0, 0.0
                    self.speed = 0.0

            self.last = {
                "x": round(self.x, 3), "y": round(self.y, 3), "z": round(self.z, 3), "flying": self.flying, "auto_takeoffs": self.auto_takeoffs, "ceiling_contacts": self.ceiling_contacts, "heading": round(self.heading, 4),
                "neural_loom_memory": round(self.neural_loom_memory, 2), "neural_escape_memory": round(self.neural_escape_memory, 2), "neural_flight_memory": round(self.neural_flight_memory, 2),
                "speed": round(self.speed, 2), "raw_throttle": brain.y, "raw_steering": brain.x,
                "throttle": round(control.throttle * 70), "steering": round(control.steering * 70),
                "motor_throttle_rate": round(raw_throttle * 50, 2), "motor_steering_rate": round(raw_steering * 50, 2),
                "control_source": source, "neural_escape_enabled": self.neural_escape_enabled,
                "stimulus": ",".join(sorted(self.stimulus_ticks)) or "none",
                "events": self.events[-8:],
                "left_threat": round(lc4_rate, 2), "right_threat": round(lplc2_rate, 2),
                "lc4_rate": round(lc4_rate, 2), "lplc2_rate": round(lplc2_rate, 2),
                "dnp01_rate": round(dnp01_rate, 2), "dnp10_rate": round(dnp10_rate, 2), "flight_rate": round(flight_rate, 2),
                "dng100_rate": round(dng_rate, 2), "dna_rate": round(dna_rate, 2),
                "dng100_l_rate": round(self.group_rate("DNg100_L", spikes), 2), "dng100_r_rate": round(self.group_rate("DNg100_R", spikes), 2),
                "dna02_l_rate": round(self.group_rate("DNa02_L", spikes), 2), "dng13_l_rate": round(self.group_rate("DNg13_L", spikes), 2),
                "dna02_r_rate": round(self.group_rate("DNa02_R", spikes), 2), "dng13_r_rate": round(self.group_rate("DNg13_R", spikes), 2),
                "assist": source != "MaleCNS", "safe_mode": False,
                "distance": round(self.distance, 2), "collisions": self.collisions,
                "wall_collisions": self.wall_collisions, "last_contact": self.last_contact,
                "visible_objects": visible_objects, "object_count": len(OBJECTS),
                "box_successes": self.box_successes,
                "spikes": int(len(spikes)), "step": self.model.step_count, "paused": self.paused,
                "neurons": self.model.n, "edges": int(self.model.w.nnz),
            }

    def state(self):
        with self.lock: return dict(self.last)


WORLD: World | None = None


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
            parsed = urlparse(self.path)
            if parsed.path == "/reset": WORLD.reset()
            elif parsed.path == "/pause": WORLD.paused = not WORLD.paused
            elif parsed.path == "/neural-escape": WORLD.neural_escape_enabled = not WORLD.neural_escape_enabled
            elif parsed.path == "/flight-test":
                for name in ("DNp01", "DNp02", "DNp04", "DNp11"):
                    WORLD.stimulus_ticks[name] = 100
                WORLD.events.append({"time": round(time.time(), 2), "type": "flight-test", "group": "DNp01+DNp02+DNp04+DNp11"})
            elif parsed.path == "/stimulate":
                name = parse_qs(parsed.query).get("group", [""])[0]
                if name not in WORLD.neuron_groups: self.send_response(400); self.end_headers(); return
                WORLD.stimulus_ticks[name] = 20  # 400 ms at 50 Hz
                WORLD.events.append({"time": round(time.time(), 2), "type": "stimulus", "group": name})
            elif parsed.path == "/escape-test":
                for name in ("LC4", "LPLC2"):
                    WORLD.stimulus_ticks[name] = 20
                WORLD.events.append({"time": round(time.time(), 2), "type": "escape-test", "group": "LC4+LPLC2"})
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
    WORLD = World()
    threading.Thread(target=loop, daemon=True).start()
    print(f"Jianqing's FlyBobotCar: http://127.0.0.1:{PORT}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
