"""Fixed-Time Traffic Signal Controller.

Executes a deterministic cyclic timing plan with predefined green and yellow
durations for compatible movement phases, ensuring safe clearance intervals.
"""

from __future__ import annotations

from typing import Any, Dict

from configs.default_config import DEFAULT_SIM_CONFIG, SimulationConfig
from controllers.base_controller import BaseTrafficController


class FixedTimeController(BaseTrafficController):
    """Cyclic fixed-time controller with safety transitions."""

    def __init__(
        self,
        green_time_ns: int = 35,
        green_time_ew: int = 35,
        yellow_time: int = 3,
        config: SimulationConfig = DEFAULT_SIM_CONFIG,
    ) -> None:
        super().__init__(name="FixedTimeController")
        self.green_time_ns = green_time_ns
        self.green_time_ew = green_time_ew
        self.yellow_time = yellow_time
        self.config = config

        # Phase cycle: (phase_index, duration)
        # 0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow
        self.cycle = [
            (self.config.phase_ns_green, self.green_time_ns),
            (self.config.phase_ns_yellow, self.yellow_time),
            (self.config.phase_ew_green, self.green_time_ew),
            (self.config.phase_ew_yellow, self.yellow_time),
        ]
        self.cycle_index = 0
        self.phase_elapsed = 0

    def reset(self) -> None:
        """Reset cycle timer to start of NS green."""
        self.cycle_index = 0
        self.phase_elapsed = 0

    def step(self, current_time: int, state: Dict[str, Any]) -> int:
        """Advance timing cycle and return current or transitioned phase."""
        current_target_phase, target_duration = self.cycle[self.cycle_index]

        # Check if current phase duration has elapsed
        if self.phase_elapsed >= target_duration:
            # Advance to next phase in cyclic sequence
            self.cycle_index = (self.cycle_index + 1) % len(self.cycle)
            self.phase_elapsed = 0
            current_target_phase, _ = self.cycle[self.cycle_index]

        self.phase_elapsed += 1
        return current_target_phase
