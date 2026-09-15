# Jianqing's FlyBobotCar

A true WebGL 3D room explored by a robot car using the MaleCNS fruit-fly model. It is both a runnable demonstration and a reference implementation for connecting MaleCNS to another simulated or physical environment.

![Jianqing's FlyBobotCar dashboard](docs/flyrobotcar.png)

## Documentation

- [Architecture and data contracts](docs/ARCHITECTURE.md)
- [Build a new MaleCNS environment adapter](docs/BUILDING-NEW-ADAPTER.md)
- [Coding-agent instructions](AGENTS.md)
- [OpenCLI/X findings and neuron test plan](docs/TWITTER-FINDINGS.md)

```text
3D room + furniture → six-face camera → simulated compound eye
→ 166,700-neuron MaleCNS → motor readout + optional fly-style reflexes
→ throttle/steering → 3D robot car
```

## Requirements

- Apple Silicon macOS (the current tested platform)
- Homebrew and Git
- About 2 GB of free disk space
- Internet access for Three.js and the MaleCNS data download

## Setup and run

```bash
git clone git@github.com:pjq/FlyRobotCar.git
cd FlyRobotCar
./setup.sh       # clones Fly64, installs Python dependencies, prepares MaleCNS data
./run.sh
```

`setup.sh` downloads approximately 1.2 GB of MaleCNS source data. If you already have Fly64 prepared elsewhere, set `FLY64_DIR=/path/to/fly` instead.

Open <http://127.0.0.1:8775/>.

## Room

The bounded room contains physical walls, a sofa, coffee table, dining table, bookshelf, armchair, plant, tiled floor, and a `Jianqing's FlyBobotCar` wall sign. The backend physics, fly-camera rendering, and Three.js scene use the same object layout.

## Controls

- Drag: orbit camera
- Wheel: zoom
- Right-drag: pan
- **Reset**: manually return the car to its initial position
- **Pause / Resume**: pause simulation
- **Visual avoidance reflex**: toggle the collision-avoidance layer

## Runtime architecture

The Python process owns the authoritative room, vehicle physics, sensory rendering, MaleCNS stepping, and control decisions. The browser is a Three.js viewer that receives the same furniture list and current telemetry over HTTP.

Endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /state` | Vehicle pose, raw and applied controls, threats, contacts, and model metrics |
| `GET /vision` | Raw `256 × 128 × 3` RGB compound-eye preview |
| `GET /objects` | Authoritative furniture definitions used by Three.js |
| `POST /reset` | Reset vehicle pose and counters |
| `POST /pause` | Pause or resume the simulation |
| `POST /avoidance` | Enable or disable visual/tactile reflexes |

## Autonomous control

The raw MaleCNS readout provides throttle and steering. The optional avoidance layer estimates left/right visual threat from approaching room geometry:

- obstacle looming on the left → turn right and slow down
- obstacle looming on the right → turn left and slow down
- physical contact → short tactile escape pivot, then return to visual/MaleCNS control

The dashboard separately reports the raw brain output, applied command, left/right threat, and active control source (`MaleCNS`, `visual avoidance reflex`, or `tactile escape reflex`). There is no road-following or navigation target.

The connectome is fixed and is not trained. The sensor encoder, neuron dynamics, output decoder, visual/tactile reflexes, and vehicle physics are engineered approximations.

## Extend or reuse

The project is intentionally small: the environment adapter is contained in `robot.py`, and the viewer is a single `index.html`. To add furniture, extend `OBJECTS`; to connect another game or robot, preserve the observation → MaleCNS → action loop and replace the environment/actuator adapter.

See [Building a New MaleCNS Environment Adapter](docs/BUILDING-NEW-ADAPTER.md) for a minimal loop, coordinate conventions, output mappings, experiment design, physical-robot precautions, and an agent completion checklist.

## Verification

```bash
python3 -m py_compile robot.py
./run.sh
curl -fsS http://127.0.0.1:8775/state | jq
curl -fsS http://127.0.0.1:8775/objects | jq
curl -fsS http://127.0.0.1:8775/vision | wc -c
```

The vision endpoint should return exactly `98304` bytes.
