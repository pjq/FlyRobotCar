import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import robot


def test_room_objects_have_collision_geometry():
    assert len(robot.OBJECTS) == 13
    for item in robot.OBJECTS:
        assert item["w"] > 0 and item["d"] > 0 and item["h"] > 0
        assert robot.collides_object(item["x"], item["y"]) is not None


def test_room_start_is_free():
    assert robot.collides_object(0.0, -9.5) is None


def test_angle_wrap_is_bounded():
    assert -math.pi <= robot.wrap_angle(100.0) <= math.pi
    assert abs(abs(robot.wrap_angle(math.pi * 3)) - math.pi) < 1e-9


def test_car_radius_can_reach_room_boundaries():
    assert robot.ROOM_HALF > robot.CAR_RADIUS
    assert not robot.collides_object(0.0, -robot.ROOM_HALF + robot.CAR_RADIUS + 0.1)


def test_visual_threat_is_higher_near_a_wall():
    world = robot.World.__new__(robot.World)
    world.x, world.y, world.heading = 0.0, 0.0, math.pi / 2
    far = world.visual_threat(0.0)
    world.y = robot.ROOM_HALF - 0.2
    near = world.visual_threat(0.0)
    assert near > far


def test_three_control_modes_are_observable_in_source():
    source = (ROOT / "robot.py").read_text()
    for mode in ("MaleCNS", "MaleCNS neural escape", "LC4", "LPLC2", "DNp01", "DNp10"):
        assert mode in source
