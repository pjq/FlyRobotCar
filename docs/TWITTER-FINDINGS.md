# OpenCLI/X Findings: Candidate Neurons and Experiments

This document records the OpenCLI searches performed against the logged-in X/Twitter session on 2026-09-15. It is a lead-generation document, not a scientific literature review. X posts can be incomplete, exaggerated, synthetic, or wrong; claims below must be verified against source code and peer-reviewed work before being treated as facts.

## Search method

OpenCLI commands used:

```bash
opencli twitter search '"DNa02" fly brain' --product live --limit 20 --top-by-engagement 10 -f json
opencli twitter search '"DNg100" fly brain' --product live --limit 20 --top-by-engagement 10 -f json
opencli twitter search '"DNp01" OR "DNp10" fruit fly brain' --product live --limit 20 --top-by-engagement 10 -f json
opencli twitter search '"PPL101" DOOMFLY OR fruit fly' --product live --limit 20 --top-by-engagement 10 -f json
```

## Strongest practical leads

### 1. Looming/escape: LC4, LPLC2, DNp01

Several X posts describe a common experiment:

```text
approaching/looming visual stimulus
    → LC4 / LPLC2 visual pathway
    → MaleCNS simulation
    → DNp01 output
    → dodge / escape action
```

Relevant posts:

- [FlappyFly by @superalesha](https://x.com/i/status/2098081342416154670) — claims LC4 neurons detect an approaching pipe and DNp01 triggers a wing/escape action.
- [FLINCH demo by @MKhordoo](https://x.com/i/status/2099544722515607924) — describes `LC4 + LPLC2` input and the first DNp01 spike as a dodge trigger.
- [TheScienceLoop Chrome Dino demo](https://x.com/i/status/2098882531408187561) — describes looming expansion, LC4/LPLC2, a leaky integrate-and-fire network, and DNp01 as a jump trigger.

**Use in FlyBobotCar:**

- Construct a controlled expanding obstacle in the room camera.
- Record LC4/LPLC2 activity and DNp01 spike timing.
- Compare intact, LC4/LPLC2-silenced, and DNp01-silenced runs.
- Use the result to test an escape response, not to claim consciousness or autonomous understanding.

**Status:** biologically motivated and useful for testing, but the X posts are not sufficient validation. Verify cell-type names and mappings against MaleCNS annotations and primary literature.

### 2. Locomotion: DNg100

An X post with high engagement explicitly cautions that DNg100 is one of the neuron groups mapped to specific fly motions:

- [@linguinelabs discussion](https://x.com/i/status/2096487331096391762)

**Use in FlyBobotCar:**

```text
DNg100 activity → forward/throttle command
```

This is already the current base output mapping. The important distinction is that the mapping to a car throttle is engineered; DNg100 does not naturally emit a numeric throttle value.

### 3. Steering: DNa02 and DNg13

The X searches repeatedly associate DNa02 and DNg13 with turning/steering readouts, including the Fly64-style experiments.

**Use in FlyBobotCar:**

```text
right-side activity − left-side activity → steering command
```

Keep left and right populations separate in telemetry. A single combined activity value hides the directional signal.

### 4. Reward/plasticity: PAM, PPL1/PPL101, MBON/KC

A long-form X post describes an experiment that injects artificial dopamine into PAM neurons and changes KC→MBON synapses:

- [FlyTok experiment by @sopersone](https://x.com/i/status/2098359568799834310)

DOOMFLY-related X discussion also mentions PPL101 as an aversive/damage signal:

- [DOOMFLY discussion](https://x.com/i/status/2099142265893728327)

**Use in a later FlyBobotCar phase:**

```text
collision → aversive signal
clear passage/success → reward signal
reward/punishment → explicit plasticity rule
```

This would change the experiment from a fixed-connectome model to a plastic network or a model with a trained external readout. It must be reported separately from Raw MaleCNS mode.

**Status:** interesting research direction, but the social-media claims are not independently verified here. Do not connect a wallet, financial account, or real hardware to an experimental reward loop.

## Candidate test matrix

| Test | Input | Population to observe | Output | Ablation |
|---|---|---|---|---|
| Forward motion | Open room / visual flow | DNg100 | Throttle | Silence DNg100 |
| Left/right steering | Object entering one side | DNa02/DNg13 left/right | Steering | Silence one side |
| Looming escape | Expanding obstacle | LC4/LPLC2 → DNp01 | Dodge/brake | Silence input or output |
| Tactile escape | Furniture contact | DNp01/DNp10 or engineered contact event | Pivot | Disable tactile layer |
| Reward learning | Success/collision event | PAM / PPL1 + KC/MBON | Plasticity | Freeze weights |

## Required telemetry

For every trial, record:

```text
random seed
timestamp
sensor frame sequence
left/right visual input
LC4 activity
LPLC2 activity
DNp01/DNp10 spikes
DNg100 activity
DNa02/DNg13 left/right activity
raw throttle and steering
applied throttle and steering
control source
collision/contact event
episode outcome
```

The current FlyBobotCar API already exposes:

- `GET /state`
- `GET /vision`
- `GET /objects`
- `POST /reset`
- `POST /pause`
- `POST /avoidance`

The next implementation step for neuron-level testing is to retain named cell-type groups in the prepared MaleCNS metadata and expose their rates in `/state`.

## Interpretation rules

### What can be claimed

- A fixed MaleCNS-derived numerical network produced a measurable output.
- A selected neuron population correlated with a simulated action.
- Silencing a population changed the output under a controlled stimulus.
- An engineered interface translated neural activity into a vehicle command.

### What cannot be claimed from these demos alone

- The fly understood the game or room.
- The simulation is conscious.
- A game was learned without checking whether an external readout or script was trained.
- A connectome alone guarantees collision-free navigation.
- A social-media video proves the reported code, data, or benchmark.

## Recommended next build

Create a `Reflex Lab` view with three toggles:

```text
Raw MaleCNS
Looming escape (LC4/LPLC2 → DNp01)
Plasticity/reward experiment
```

The view should show the raw brain command, every override, neuron-group activity, and the car outcome side by side. This makes the FlyBobotCar reusable as an experiment rather than just a visual demo.
