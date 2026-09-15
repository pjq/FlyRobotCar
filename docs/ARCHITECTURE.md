# Architecture

## Purpose

Jianqing's FlyBobotCar is an educational closed-loop embodiment experiment. It connects a numerical model derived from the MaleCNS fruit-fly connectome to a virtual robot car inside a Three.js room.

It is intentionally explicit about which parts come from biological data and which parts are engineered.

```text
┌──────────────────────── 3D room ────────────────────────┐
│ walls · furniture · vehicle pose · collision geometry  │
└───────────────────────────┬─────────────────────────────┘
                            │ RGB sensor atlas
                            ▼
┌──────────────────── compound-eye adapter ──────────────┐
│ six cube faces → approximate fly receptor samples      │
└───────────────────────────┬─────────────────────────────┘
                            │ sensory current
                            ▼
┌──────────────────── MaleCNS simulation ────────────────┐
│ 166,700 neurons · 25,582,938 weighted connections      │
│ fixed connectome · modeled LIF dynamics                │
└───────────────────────────┬─────────────────────────────┘
                            │ descending-neuron activity
                            ▼
┌──────────────────── control adapters ──────────────────┐
│ DNg100 → throttle · DNa02/DNg13 → steering             │
│ LC4/LPLC2 → DNp01/DNp10 neural escape readout         │
└───────────────────────────┬─────────────────────────────┘
                            │ applied command
                            ▼
┌──────────────────── vehicle simulation ────────────────┐
│ acceleration · heading · position · object collisions  │
└───────────────────────────┬─────────────────────────────┘
                            └──────── closed loop ────────►
```

## Repository structure

| Path | Responsibility |
|---|---|
| `robot.py` | Authoritative world state, RGB sensor rendering, MaleCNS stepping, control logic, collision physics, and HTTP API |
| `index.html` | Three.js room, dashboard, fly-eye preview, controls, and telemetry polling |
| `setup.sh` | Clones the upstream Fly64 dependency and prepares MaleCNS data |
| `run.sh` | Resolves Fly64, selects its Python environment, and starts the server |
| `.gitignore` | Excludes the 1.2 GB dataset, dependency checkout, caches, logs, and runtime files |
| `docs/flyrobotcar.png` | README screenshot |

## Runtime processes

FlyBobotCar is one Python process containing two threads:

1. A simulation thread running at a target interval of 20 ms (50 Hz).
2. A `ThreadingHTTPServer` serving the UI and telemetry.

The browser runs the Three.js renderer independently and polls telemetry.

## Coordinate systems

Backend world:

- `x`: horizontal room axis
- `y`: depth axis
- `heading`: radians; `0` points toward positive `x`

Three.js world:

- backend `x` → Three.js `x`
- backend `y` → Three.js `z`
- vertical axis → Three.js `y`

Vehicle transform:

```javascript
car.position.set(state.x, 0, state.y)
car.rotation.y = -state.heading - Math.PI / 2
```

## Authoritative room model

`OBJECTS` in `robot.py` is the source of truth for furniture:

```python
{
    "kind": "sofa",
    "x": -7.0,
    "y": 5.0,
    "w": 5.0,
    "d": 2.0,
    "h": 1.6,
    "color": [47, 105, 155],
}
```

The same list drives:

- backend collision boxes;
- camera projection into the fly sensor;
- Three.js furniture construction through `GET /objects`.

This prevents visual objects and physical objects from silently diverging.

Supported specialized `kind` values in the current UI are:

- `sofa`
- `armchair`
- `coffee table`
- `dining table`
- `bookshelf`
- `plant`

Unknown kinds currently use the plant fallback. Add an explicit renderer branch when introducing a new kind.

## Sensor pipeline

`World.render_camera()` creates a `384 × 256 × 3` uint8 RGB atlas with six `128 × 128` cube faces:

```text
forward | right | back
left    | up    | down
```

It renders approximations of:

- room walls;
- ceiling and tiled floor;
- furniture color, angular position, apparent width, and apparent height.

`FlyModel` passes this atlas through the upstream `SphericalRetina`, which maps it to visual receptor neurons. `/vision` returns the resulting two-eye preview as raw `256 × 128 × 3` RGB bytes.

This renderer is intentionally lightweight. It is coherent with room geometry but is not a photorealistic Three.js framebuffer capture.

## MaleCNS model

The model is imported from the upstream Fly64 checkout:

```python
from fly64.model import FlyModel
model = FlyModel(FLY_DIR / ".cache" / "malecns")
```

Current prepared model:

- 166,700 neurons
- 25,582,938 weighted edges
- 20 ms model step
- fixed connectome-derived sparse matrix
- simplified leaky integrate-and-fire dynamics

The upstream model maps:

- `DNg100` activity to forward throttle;
- left/right `DNa02` and `DNg13` differences to steering;
- `DNp01` and `DNp10` to jump, which this car does not use.

## Control layers

### Raw MaleCNS

```python
raw_throttle = max(0, brain.y / 70)
raw_steering = clip(brain.x / 70, -1, 1)
```

### Neural escape readout

The current experiment does not use room geometry to choose a steering direction. After each full MaleCNS step, it observes named cell-type populations:

- `LC4` and `LPLC2`: visual looming-path candidates;
- `DNp01` and `DNp10`: escape-output candidates.

When their measured activity passes the experiment threshold, the car applies a reduced-throttle escape command using the neural steering readout. The active source is reported as `MaleCNS neural escape`.

This is an engineered readout/interface around the connectome, not a claim that the car has learned collision avoidance. Physical walls and furniture still stop the simulated car and record collisions, but they do not choose the action.

The UI reports one of:

- `MaleCNS`
- `MaleCNS neural escape`

## Vehicle physics

The vehicle uses a lightweight kinematic model:

```python
target_speed = throttle * MAX_SPEED
speed += (target_speed - speed) * 0.12
heading += steering * turn_rate * DT
x += cos(heading) * speed * DT
y += sin(heading) * speed * DT
```

Walls and furniture are physical collision constraints. Contact stops translation. The tactile reflex can pivot the robot away if enabled.

## HTTP API

### `GET /`

Returns the dashboard.

### `GET /state`

Returns current telemetry. Important fields:

```json
{
  "x": 1.2,
  "y": -3.4,
  "heading": 1.57,
  "speed": 2.8,
  "raw_throttle": 55,
  "raw_steering": -12,
  "throttle": 27,
  "steering": 35,
  "control_source": "visual avoidance reflex",
  "left_threat": 0.7,
  "right_threat": 0.1,
  "last_contact": "none",
  "visible_objects": 3,
  "collisions": 1
}
```

### `GET /vision`

Returns raw RGB bytes:

- width: 256
- height: 128
- channels: RGB
- byte count: 98,304

### `GET /objects`

Returns the authoritative room object list.

### `POST /reset`

Resets vehicle pose and run counters.

### `POST /pause`

Toggles simulation pause.

### `POST /neural-escape`

Toggles the `LC4/LPLC2 → DNp01/DNp10` neural escape readout for ablation/control comparisons. It does not enable a geometry-based safety controller.

## Truthful interpretation

Biological-data-derived:

- neuron identities and annotations;
- connectome topology;
- synapse-derived weights;
- selected visual and descending-neuron groups.

Engineered:

- RGB room renderer;
- compound-eye angular registration;
- LIF dynamics and constants;
- throttle/steering decoder;
- vehicle physics;
- named-neuron escape threshold and motor readout;
- all UI and telemetry.

The application is not evidence of consciousness, understanding, or a biologically complete brain upload.
