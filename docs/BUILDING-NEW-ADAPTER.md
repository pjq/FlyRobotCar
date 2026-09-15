# Building a New MaleCNS Environment Adapter

This guide is for developers and coding agents that want to reuse FlyBobotCar as a starting point for a new game, robot, simulation, or visualization.

## The minimum contract

Every environment adapter needs four stages:

```text
observe environment
→ encode sensory input
→ step MaleCNS model
→ decode and apply an action
```

Minimal Python loop:

```python
from pathlib import Path
from fly64.model import FlyModel

model = FlyModel(Path("/path/to/fly/.cache/malecns"))

while True:
    atlas = environment.render_six_faces()  # uint8, shape (256, 384, 3)
    control, spikes = model.step(atlas)
    environment.apply(
        throttle=control.y / 70.0,
        steering=control.x / 70.0,
        trigger=control.jump,
    )
```

## Step 1: choose an environment

Good first adapters have:

- a continuous observation stream;
- one or two movement axes;
- deterministic physics;
- resettable episodes;
- measurable outcomes.

Examples:

- 2D obstacle avoidance
- WebGL room navigation
- maze exploration
- light seeking
- simulated differential-drive robot
- small physical robot with a speed-limited safety layer

Avoid starting with high-speed drones, vehicles, or dangerous hardware.

## Step 2: implement visual observations

`FlyModel.step()` currently expects:

```text
shape: (256, 384, 3)
dtype: uint8
layout: six 128×128 cube faces
faces: forward, right, back, left, up, down
```

A new adapter can:

1. Render six cameras directly.
2. Capture one camera and synthesize the other directions.
3. Replace `SphericalRetina` with a new encoder, provided the model receives one value per visual neuron.

Keep the visual path independent from privileged state. Do not feed object coordinates directly into a component claimed to be vision-driven.

Recommended checks:

```python
assert atlas.shape == (256, 384, 3)
assert atlas.dtype == np.uint8
assert np.unique(atlas.reshape(-1, 3), axis=0).shape[0] > 1
```

## Step 3: choose output neurons

The upstream model exposes:

```python
model.forward
model.turn_left
model.turn_right
model.jump_nodes
```

Current interpretation:

| Population | Adapter interpretation |
|---|---|
| DNg100 | forward/throttle |
| DNa02 + DNg13 left | left steering activity |
| DNa02 + DNg13 right | right steering activity |
| DNp01 + DNp10 | jump/trigger event |

Do not claim these populations naturally represent gamepad buttons. The mapping is an engineered embodiment interface.

## Step 4: separate raw and applied controls

Always preserve both:

```python
raw = model.step(observation)
applied = safety_or_task_adapter(raw)
```

Telemetry should say which layer produced the final command:

```json
{
  "raw_throttle": 52,
  "raw_steering": -8,
  "throttle": 24,
  "steering": 31,
  "control_source": "visual avoidance reflex"
}
```

This prevents an engineered controller from being mistaken for a capability learned by the connectome.

## Step 5: decide the experimental mode

### Raw mode

Apply the MaleCNS-derived readout directly.

Use this to answer:

- What behavior emerges without intervention?
- Does the output correlate with visual changes?
- Does the system stop, oscillate, or collide?

Failures are valid results.

### Reflex mode

Add narrow biologically inspired reactions such as:

- looming avoidance;
- touch-triggered turning;
- light seeking;
- speed reduction near visual expansion.

Label the active reflex explicitly.

### Safety-shield mode

For physical hardware, predict collisions and reject unsafe commands. The fly provides intent; conventional code enforces safety. Never describe this as fly-only control.

## Step 6: use one authoritative world model

Do not separately hardcode objects in physics, rendering, and telemetry.

Recommended pattern:

```python
OBJECTS = [{"kind": "box", "x": 1, "y": 2, "w": 1, "d": 1, "h": 1}]
```

Use the same collection for:

- collision checks;
- sensor rendering;
- browser/engine rendering;
- debugging output.

FlyBobotCar exposes this through `GET /objects`.

## Step 7: define measurable experiments

Examples:

- collision count per minute;
- distance traveled before first collision;
- percentage of time moving;
- left/right response to a controlled looming stimulus;
- raw mode versus reflex mode;
- intact network versus silenced neuron populations;
- repeated trials with fixed random seeds.

Do not evaluate only a selected successful video. Save complete runs and report failures.

## Adding a new room object

Add it once to `OBJECTS` in `robot.py`:

```python
{
    "kind": "lamp",
    "x": 3.0,
    "y": -2.0,
    "w": 0.8,
    "d": 0.8,
    "h": 2.0,
    "color": [220, 190, 90],
}
```

Then add a `lamp` branch to `addFurniture()` in `index.html`. Collision and fly-camera projection already consume the shared object fields.

## Replacing the browser environment

The browser is only a viewer. A Unity, Godot, MuJoCo, or native application can replace it while keeping the Python model.

Recommended transport options:

- local WebSocket for browser engines;
- UDP for low-latency simulations;
- shared memory for native processes on one machine;
- ROS 2 topics for robots;
- recorded NPZ files for deterministic replay.

Define an explicit schema containing:

```text
timestamp
frame sequence
sensor image or feature vector
raw neural output
applied command
pose
event/contact state
```

## Physical robot checklist

Before connecting real motors:

- enforce maximum speed and turn rate;
- add an independent emergency stop;
- stop on stale heartbeat;
- use a physical bumper or range sensor;
- test inside a bounded low-energy enclosure;
- keep safety logic outside model control;
- log raw and applied commands separately.

## Verification commands

```bash
python3 -m py_compile robot.py
curl -fsS http://127.0.0.1:8775/state | jq
curl -fsS http://127.0.0.1:8775/objects | jq
curl -fsS http://127.0.0.1:8775/vision | wc -c  # expected: 98304
```

Check the UI JavaScript syntax:

```bash
python3 - <<'PY'
from pathlib import Path
import re, subprocess
html = Path('index.html').read_text()
js = re.search(r'<script type="module">(.*?)</script>', html, re.S).group(1)
js = re.sub(r'^import .*?;\\s*', '', js)
Path('/tmp/flyrobotcar.js').write_text(js)
subprocess.run(['node', '--check', '/tmp/flyrobotcar.js'], check=True)
PY
```

## Agent implementation checklist

Before declaring a new adapter complete:

- [ ] Read `README.md` and `docs/ARCHITECTURE.md`.
- [ ] Verify the prepared MaleCNS cache exists.
- [ ] Keep generated datasets and dependency checkouts out of Git.
- [ ] Use one authoritative object/world representation.
- [ ] Validate observation dimensions and dtype.
- [ ] Expose raw and applied controls separately.
- [ ] Label every non-MaleCNS intervention.
- [ ] Add a deterministic reset.
- [ ] Add measurable outcome counters.
- [ ] Test syntax and HTTP endpoints.
- [ ] Document biological-data-derived versus engineered components.
- [ ] Never include copyrighted ROMs or private credentials.
