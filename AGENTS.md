# Agent Guide

Before modifying this project, read completely:

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/BUILDING-NEW-ADAPTER.md`

## Project invariants

- `robot.py` owns world state and physics.
- `OBJECTS` is the authoritative furniture list; `/objects` supplies it to Three.js.
- Backend coordinates `(x, y)` map to Three.js `(x, z)`.
- Fly vision must be derived from the represented environment, not privileged object labels or target coordinates.
- Keep raw MaleCNS output separate from applied controls.
- Every override must have a visible `control_source` value.
- Do not describe engineered reflexes as trained or emergent MaleCNS behavior.
- Do not commit `.deps/`, MaleCNS datasets, virtual environments, runtime logs, PIDs, secrets, or copyrighted ROMs.

## Required verification

```bash
python3 -m py_compile robot.py
./run.sh
curl -fsS http://127.0.0.1:8775/state | jq
curl -fsS http://127.0.0.1:8775/objects | jq
curl -fsS http://127.0.0.1:8775/vision | wc -c
```

Expected vision payload: `98304` bytes.

When changing UI JavaScript, also run the syntax-check snippet in `docs/BUILDING-NEW-ADAPTER.md` and verify the WebGL scene in a browser.
