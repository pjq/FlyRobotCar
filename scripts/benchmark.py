#!/usr/bin/env python3
"""Run short raw-vs-reflex trials against a running FlyBobotCar server."""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8775"
TRIAL_SECONDS = 8


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=3) as response:
        return json.load(response)


def post(path):
    request = urllib.request.Request(BASE + path, method="POST")
    with urllib.request.urlopen(request, timeout=3):
        pass


def run(name, avoidance):
    state = get("/state")
    if bool(state.get("avoidance_enabled")) != avoidance:
        post("/avoidance")
    post("/reset")
    start = time.monotonic()
    samples = []
    while time.monotonic() - start < TRIAL_SECONDS:
        sample = get("/state")
        if "speed" in sample:
            samples.append(sample)
        time.sleep(.25)
    if not samples:
        raise RuntimeError("server did not publish telemetry during trial")
    final = samples[-1]
    return {
        "mode": name,
        "seconds": TRIAL_SECONDS,
        "distance": final["distance"],
        "collisions": final["collisions"],
        "wall_collisions": final["wall_collisions"],
        "stopped_samples": sum(s["speed"] == 0 for s in samples),
        "final_contact": final["last_contact"],
        "visible_objects": final["visible_objects"],
    }


if __name__ == "__main__":
    results = [run("raw MaleCNS", False), run("MaleCNS + visual/tactile reflex", True)]
    print(json.dumps({"experiment": "room navigation", "results": results}, indent=2))
