# Jianqing's FlyBobotCar

A true WebGL 3D room explored by a robot car using the MaleCNS fruit-fly model.

![Jianqing's FlyBobotCar dashboard](docs/flyrobotcar.png)

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

## Autonomous control

The raw MaleCNS readout provides throttle and steering. The optional avoidance layer estimates left/right visual threat from approaching room geometry:

- obstacle looming on the left → turn right and slow down
- obstacle looming on the right → turn left and slow down
- physical contact → short tactile escape pivot, then return to visual/MaleCNS control

The dashboard separately reports the raw brain output, applied command, left/right threat, and active control source (`MaleCNS`, `visual avoidance reflex`, or `tactile escape reflex`). There is no road-following or navigation target.

The connectome is fixed and is not trained. The sensor encoder, neuron dynamics, output decoder, visual/tactile reflexes, and vehicle physics are engineered approximations.
