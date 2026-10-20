"""Abstract Base Class for all Traffic Signal Controllers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTrafficController(ABC):
    """Base interface for traffic signal controllers."""

    def __init__(self, name: str = "BaseController") -> None:
        self.name = name

    @abstractmethod
    def step(self, current_time: int, state: Dict[str, Any]) -> int:
        """Compute and return the desired traffic light phase index.

        Args:
            current_time: Current simulation time in seconds.
            state: Dictionary containing current traffic state:
                - 'current_phase': int
                - 'phase_duration': int
                - 'queues': dict of queue lengths per edge/lane
                - 'waiting_times': dict of waiting times per edge/lane
                - 'vehicle_counts': dict of vehicle counts per edge
                - 'max_waiting_time': float max wait time across vehicles
                - 'edge_data': dict mapping edge_id to metrics

        Returns:
            The phase index (0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow)
            that the controller requests.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal controller timers and state for a new episode/run."""
        pass
