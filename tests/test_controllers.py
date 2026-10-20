"""Unit tests for Fixed-Time and Adaptive traffic controllers."""

import pytest

from configs.default_config import AdaptiveConfig, DEFAULT_ADAPTIVE_CONFIG, DEFAULT_SIM_CONFIG
from controllers.adaptive import AdaptiveController
from controllers.fixed_time import FixedTimeController


def test_fixed_time_cycle():
    """Verify cyclic phase transitions and yellow timing in fixed controller."""
    ctrl = FixedTimeController(green_time_ns=10, green_time_ew=10, yellow_time=3)
    dummy_state = {}

    # Initial phase should be NS Green (0) for 10 steps
    for t in range(10):
        phase = ctrl.step(t, dummy_state)
        assert phase == DEFAULT_SIM_CONFIG.phase_ns_green

    # Next 3 steps should be NS Yellow (1)
    for t in range(10, 13):
        phase = ctrl.step(t, dummy_state)
        assert phase == DEFAULT_SIM_CONFIG.phase_ns_yellow

    # Next 10 steps should be EW Green (2)
    for t in range(13, 23):
        phase = ctrl.step(t, dummy_state)
        assert phase == DEFAULT_SIM_CONFIG.phase_ew_green

    # Next 3 steps should be EW Yellow (3)
    for t in range(23, 26):
        phase = ctrl.step(t, dummy_state)
        assert phase == DEFAULT_SIM_CONFIG.phase_ew_yellow

    # Then returns to NS Green (0)
    assert ctrl.step(26, dummy_state) == DEFAULT_SIM_CONFIG.phase_ns_green


def test_adaptive_min_green_safeguard():
    """Ensure adaptive controller respects min_green even with high opposing queue."""
    cfg = AdaptiveConfig(min_green=10, max_green=50, yellow_time=3)
    ctrl = AdaptiveController(adaptive_config=cfg)

    # Opposing approach has massive queue, but min green not elapsed yet
    state_high_opposing = {
        "queues": {"N": 0, "S": 0, "E": 20, "W": 20},
        "waiting_times": {"N": 0.0, "S": 0.0, "E": 200.0, "W": 200.0},
        "max_waiting_time": 30.0,
    }

    for t in range(9):
        phase = ctrl.step(t, state_high_opposing)
        assert phase == DEFAULT_SIM_CONFIG.phase_ns_green, "Min green safeguard violated"

    # Step 10: min green has elapsed, should trigger yellow switch to EW
    phase = ctrl.step(10, state_high_opposing)
    assert phase == DEFAULT_SIM_CONFIG.phase_ns_yellow


def test_adaptive_max_green_safeguard():
    """Ensure adaptive controller forces phase change when max_green is reached."""
    cfg = AdaptiveConfig(min_green=10, max_green=20, yellow_time=3)
    ctrl = AdaptiveController(adaptive_config=cfg)

    # Current approach has lots of traffic
    state_busy_ns = {
        "queues": {"N": 10, "S": 10, "E": 2, "W": 2},
        "waiting_times": {"N": 100.0, "S": 100.0, "E": 10.0, "W": 10.0},
        "max_waiting_time": 15.0,
    }

    # Run up to max_green
    for t in range(19):
        ctrl.step(t, state_busy_ns)

    # At step 20, should switch to yellow
    phase = ctrl.step(20, state_busy_ns)
    assert phase == DEFAULT_SIM_CONFIG.phase_ns_yellow


def test_adaptive_starvation_safeguard():
    """Ensure waiting vehicle starvation triggers priority switch."""
    cfg = AdaptiveConfig(min_green=5, max_green=50, yellow_time=3, starvation_threshold_sec=30.0)
    ctrl = AdaptiveController(adaptive_config=cfg)

    # Opposing vehicle waiting > threshold
    starving_state = {
        "queues": {"N": 5, "S": 5, "E": 1, "W": 0},
        "waiting_times": {"N": 20.0, "S": 20.0, "E": 35.0, "W": 0.0},
        "max_waiting_time": 35.0,
    }

    for t in range(5):
        ctrl.step(t, starving_state)

    # At t=5 (after min_green), starvation must trigger yellow
    phase = ctrl.step(5, starving_state)
    assert phase == DEFAULT_SIM_CONFIG.phase_ns_yellow
