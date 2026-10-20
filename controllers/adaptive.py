"""Adaptive Rule-Based Traffic Signal Controller.

Dynamically allocates green time based on real-time queues, vehicle counts,
and accumulated waiting times. Enforces minimum green, maximum green,
and anti-starvation safeguards with safe yellow transitions.
"""

from __future__ import annotations

from typing import Any, Dict

from configs.default_config import (
    DEFAULT_ADAPTIVE_CONFIG,
    DEFAULT_SIM_CONFIG,
    AdaptiveConfig,
    SimulationConfig,
)
from controllers.base_controller import BaseTrafficController


class AdaptiveController(BaseTrafficController):
    """Dynamic queue- and waiting-time-responsive controller with safety safeguards."""

    def __init__(
        self,
        adaptive_config: AdaptiveConfig = DEFAULT_ADAPTIVE_CONFIG,
        sim_config: SimulationConfig = DEFAULT_SIM_CONFIG,
    ) -> None:
        super().__init__(name="AdaptiveController")
        self.cfg = adaptive_config
        self.sim_cfg = sim_config

        # State machine
        # 0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow
        self.current_phase: int = self.sim_cfg.phase_ns_green
        self.phase_elapsed: int = 0
        self.yellow_timer: int = 0
        self.pending_green_phase: int = self.sim_cfg.phase_ew_green

    def reset(self) -> None:
        """Reset state machine for a new simulation run."""
        self.current_phase = self.sim_cfg.phase_ns_green
        self.phase_elapsed = 0
        self.yellow_timer = 0
        self.pending_green_phase = self.sim_cfg.phase_ew_green

    def step(self, current_time: int, state: Dict[str, Any]) -> int:
        """Evaluate traffic state and return current or transitioning phase."""
        queues = state.get("queues", {"N": 0, "S": 0, "E": 0, "W": 0})
        waiting_times = state.get("waiting_times", {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0})
        max_waiting_time = state.get("max_waiting_time", 0.0)

        # 1. Handle Yellow Transition Phase
        if self.current_phase in (self.sim_cfg.phase_ns_yellow, self.sim_cfg.phase_ew_yellow):
            self.yellow_timer += 1
            if self.yellow_timer >= self.cfg.yellow_time:
                # Transition completed: enter target green phase
                self.current_phase = self.pending_green_phase
                self.phase_elapsed = 0
                self.yellow_timer = 0
            return self.current_phase

        # 2. In Green Phase (NS or EW)
        self.phase_elapsed += 1

        is_ns_green = self.current_phase == self.sim_cfg.phase_ns_green

        # Identify current vs opposing approach queues & waits
        if is_ns_green:
            current_queue = queues.get("N", 0) + queues.get("S", 0)
            opposing_queue = queues.get("E", 0) + queues.get("W", 0)
            current_wait = waiting_times.get("N", 0.0) + waiting_times.get("S", 0.0)
            opposing_wait = waiting_times.get("E", 0.0) + waiting_times.get("W", 0.0)
            yellow_phase = self.sim_cfg.phase_ns_yellow
            next_green = self.sim_cfg.phase_ew_green
        else:
            current_queue = queues.get("E", 0) + queues.get("W", 0)
            opposing_queue = queues.get("N", 0) + queues.get("S", 0)
            current_wait = waiting_times.get("E", 0.0) + waiting_times.get("W", 0.0)
            opposing_wait = waiting_times.get("N", 0.0) + waiting_times.get("S", 0.0)
            yellow_phase = self.sim_cfg.phase_ew_yellow
            next_green = self.sim_cfg.phase_ns_green

        # Rule A: Minimum Green Safeguard (must maintain green for at least min_green)
        if self.phase_elapsed < self.cfg.min_green:
            return self.current_phase

        # Rule B: Maximum Green Safeguard (force phase change to prevent perpetual green)
        if self.phase_elapsed >= self.cfg.max_green:
            return self._initiate_yellow_switch(yellow_phase, next_green)

        # Rule C: Anti-Starvation Safeguard
        # If opposing approaches have waiting vehicles and max wait exceeds threshold
        if opposing_queue > 0 and max_waiting_time >= self.cfg.starvation_threshold_sec:
            return self._initiate_yellow_switch(yellow_phase, next_green)

        # Rule D: Urgency Pressure Comparison
        # Pressure = w_queue * queue + w_wait * (total_wait / 10)
        current_pressure = (
            self.cfg.queue_weight * current_queue
            + self.cfg.wait_time_weight * (current_wait / 10.0)
        )
        opposing_pressure = (
            self.cfg.queue_weight * opposing_queue
            + self.cfg.wait_time_weight * (opposing_wait / 10.0)
        )

        # If opposing pressure exceeds current pressure and opposing queue exists: switch
        if opposing_queue > 0 and (opposing_pressure > current_pressure or current_queue == 0):
            return self._initiate_yellow_switch(yellow_phase, next_green)

        # Otherwise extend green
        return self.current_phase

    def _initiate_yellow_switch(self, yellow_phase: int, next_green: int) -> int:
        """Trigger yellow transition interval."""
        self.current_phase = yellow_phase
        self.yellow_timer = 0
        self.pending_green_phase = next_green
        return self.current_phase
