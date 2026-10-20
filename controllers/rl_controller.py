"""Reinforcement Learning Traffic Signal Controller.

Wraps a trained Stable-Baselines3 policy (PPO/DQN) into the BaseTrafficController
interface with safe yellow transitions and real-time state extraction.
"""

from __future__ import annotations

try:
    from stable_baselines3 import PPO
except ImportError:
    PPO = None

from configs.default_config import (
    DEFAULT_RL_CONFIG,
    DEFAULT_SIM_CONFIG,
    RLConfig,
    SimulationConfig,
)
from controllers.base_controller import BaseTrafficController


class RLTrafficController(BaseTrafficController):
    """Executes trained RL policy with safe transition constraints."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        model: Optional[Any] = None,
        rl_config: RLConfig = DEFAULT_RL_CONFIG,
        sim_config: SimulationConfig = DEFAULT_SIM_CONFIG,
    ) -> None:
        super().__init__(name="RLTrafficController")
        self.rl_cfg = rl_config
        self.sim_cfg = sim_config
        self.model = model

        if self.model is None and model_path is not None:
            if PPO is None:
                raise ImportError(
                    "stable-baselines3 is required to load and run RL controllers.\n"
                    "Install it using: pip install stable-baselines3"
                )
            path = Path(model_path)
            if path.exists():
                self.model = PPO.load(str(path))
            else:
                raise FileNotFoundError(f"Model checkpoint not found at: {model_path}")

        # State machine
        # 0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow
        self.current_phase: int = self.sim_cfg.phase_ns_green
        self.current_green_choice: int = 0  # 0: NS, 1: EW
        self.phase_elapsed: int = 0
        self.yellow_timer: int = 0
        self.pending_green_phase: int = self.sim_cfg.phase_ew_green

    def reset(self) -> None:
        """Reset state machine for a new simulation run."""
        self.current_phase = self.sim_cfg.phase_ns_green
        self.current_green_choice = 0
        self.phase_elapsed = 0
        self.yellow_timer = 0
        self.pending_green_phase = self.sim_cfg.phase_ew_green

    def _format_obs(self, state: Dict[str, Any]) -> np.ndarray:
        """Format raw state dictionary into normalized 14-dim observation vector."""
        queues_dict = state.get("queues", {})
        waits_dict = state.get("waiting_times", {})
        counts_dict = state.get("vehicle_counts", {})

        queues = [min(float(queues_dict.get(arm, 0)) / 20.0, 1.0) for arm in ("N", "S", "E", "W")]
        waits = [min(float(waits_dict.get(arm, 0.0)) / 120.0, 1.0) for arm in ("N", "S", "E", "W")]
        counts = [min(float(counts_dict.get(arm, 0)) / 25.0, 1.0) for arm in ("N", "S", "E", "W")]

        active_green = 0.0 if self.current_green_choice == 0 else 1.0
        elapsed_norm = min(float(self.phase_elapsed) / float(self.sim_cfg.max_green), 1.0)

        return np.array(queues + waits + counts + [active_green, elapsed_norm], dtype=np.float32)

    def step(self, current_time: int, state: Dict[str, Any]) -> int:
        """Query policy on decision intervals and execute safe transitions."""
        # 1. Handle Yellow Transition Interval
        if self.current_phase in (self.sim_cfg.phase_ns_yellow, self.sim_cfg.phase_ew_yellow):
            self.yellow_timer += 1
            if self.yellow_timer >= self.rl_cfg.yellow_duration:
                self.current_phase = self.pending_green_phase
                self.current_green_choice = 0 if self.current_phase == self.sim_cfg.phase_ns_green else 1
                self.phase_elapsed = 0
                self.yellow_timer = 0
            return self.current_phase

        # 2. In Green Phase
        self.phase_elapsed += 1

        # Only evaluate policy at decision intervals
        if current_time % self.rl_cfg.decision_interval == 0:
            obs = self._format_obs(state)
            if self.model is not None:
                action, _ = self.model.predict(obs, deterministic=True)
                desired_green = int(action)
            else:
                desired_green = self.current_green_choice

            # Check if policy desires a phase change
            if desired_green != self.current_green_choice:
                # Initiate yellow transition
                if self.current_green_choice == 0:
                    yellow_phase = self.sim_cfg.phase_ns_yellow
                    next_green = self.sim_cfg.phase_ew_green
                else:
                    yellow_phase = self.sim_cfg.phase_ew_yellow
                    next_green = self.sim_cfg.phase_ns_green

                self.current_phase = yellow_phase
                self.yellow_timer = 0
                self.pending_green_phase = next_green
                return self.current_phase

        return self.current_phase
