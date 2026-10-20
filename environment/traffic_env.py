"""Gymnasium Traffic Signal Environment.

Wraps SUMO/TraCI in a standard Farama Gymnasium interface for Reinforcement
Learning agents (PPO, DQN, etc.), enforcing safe signal transitions and
providing rich traffic state observations and balanced rewards.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from simulation.sumo_utils import close_traci_safely, get_sumo_binary, setup_sumo_environment

# Ensure SUMO tools are available in sys.path
setup_sumo_environment()
import traci

from configs.default_config import (
    DEFAULT_RL_CONFIG,
    DEFAULT_SIM_CONFIG,
    RLConfig,
    SimulationConfig,
)
from simulation.generate_demand import generate_demand
from simulation.generate_network import generate_network


class SumoTrafficEnv(gym.Env):
    """Gymnasium environment for adaptive traffic light control."""

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(
        self,
        scenario: str = "normal",
        sim_duration: int = 1000,
        gui: bool = False,
        seed: int = 42,
        rl_config: RLConfig = DEFAULT_RL_CONFIG,
        sim_config: SimulationConfig = DEFAULT_SIM_CONFIG,
    ) -> None:
        super().__init__()
        self.scenario = scenario
        self.sim_duration = sim_duration
        self.gui = gui
        self.default_seed = seed
        self.rl_cfg = rl_config
        self.sim_cfg = sim_config

        # Action space: 0 -> North-South Green (Phase 0), 1 -> East-West Green (Phase 2)
        self.action_space = spaces.Discrete(2)

        # Observation space: 14 continuous features in [0.0, 1.0]
        # [4 queues, 4 wait_times, 4 counts, 1 active_green, 1 phase_elapsed]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(14,), dtype=np.float32
        )

        self.current_sim_time = 0
        self.current_green_phase = 0  # 0: NS Green, 1: EW Green
        self.current_tls_phase = self.sim_cfg.phase_ns_green
        self.phase_elapsed_time = 0
        self.prev_total_wait = 0.0

        # Network setup
        setup_sumo_environment()
        self.net_file = self.sim_cfg.net_file
        if not self.net_file.exists():
            self.net_file = generate_network(
                output_dir=self.sim_cfg.network_dir,
                arm_length=self.sim_cfg.arm_length,
            )

    def _get_obs(self) -> np.ndarray:
        """Extract and normalize current traffic observation."""
        queues: list[float] = []
        waits: list[float] = []
        counts: list[float] = []

        for arm in ("N", "S", "E", "W"):
            edge_id = f"{arm}_to_J0"
            try:
                q = float(traci.edge.getLastStepHaltingNumber(edge_id))
                w = float(traci.edge.getWaitingTime(edge_id))
                c = float(traci.edge.getLastStepVehicleNumber(edge_id))
            except Exception:
                q, w, c = 0.0, 0.0, 0.0

            # Normalize values
            queues.append(min(q / 20.0, 1.0))
            waits.append(min(w / 120.0, 1.0))
            counts.append(min(c / 25.0, 1.0))

        active_green = 0.0 if self.current_green_phase == 0 else 1.0
        elapsed_norm = min(float(self.phase_elapsed_time) / float(self.sim_cfg.max_green), 1.0)

        obs = np.array(queues + waits + counts + [active_green, elapsed_norm], dtype=np.float32)
        return obs

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Start a new simulation episode."""
        super().reset(seed=seed)
        run_seed = seed if seed is not None else self.default_seed

        if options and "scenario" in options:
            self.scenario = options["scenario"]

        close_traci_safely()

        # Generate scenario demand file
        route_file = generate_demand(
            scenario=self.scenario,
            duration=self.sim_duration,
            seed=run_seed,
            output_path=self.sim_cfg.scenarios_dir / f"env_{self.scenario}_s{run_seed}.rou.xml",
        )

        sumo_bin = get_sumo_binary(gui=self.gui)
        sumo_cmd = [
            sumo_bin,
            "-n", str(self.net_file),
            "-r", str(route_file),
            "--step-length", "1.0",
            "--time-to-teleport", "-1",
            "--no-step-log", "true",
            "--no-warnings", "true",
            "--seed", str(run_seed),
        ]

        if self.gui:
            view_settings = self.sim_cfg.network_dir / "viewsettings.xml"
            if view_settings.exists():
                sumo_cmd.extend(["--gui-settings-file", str(view_settings)])
            sumo_cmd.extend(["--start", "true", "--quit-on-end", "true"])

        traci.start(sumo_cmd)

        self.current_sim_time = 0
        self.current_green_phase = 0
        self.current_tls_phase = self.sim_cfg.phase_ns_green
        self.phase_elapsed_time = 0
        self.prev_total_wait = 0.0

        traci.trafficlight.setPhase(self.sim_cfg.tls_id, self.current_tls_phase)

        obs = self._get_obs()
        info: Dict[str, Any] = {"step": 0, "scenario": self.scenario}
        return obs, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute action, advance simulation by decision interval, and return transition."""
        desired_green = int(action)  # 0: NS Green, 1: EW Green
        target_tls_phase = (
            self.sim_cfg.phase_ns_green if desired_green == 0 else self.sim_cfg.phase_ew_green
        )

        # Check if phase change is requested
        if desired_green != self.current_green_phase:
            # Must transition through yellow for safety
            yellow_phase = (
                self.sim_cfg.phase_ns_yellow if self.current_green_phase == 0 else self.sim_cfg.phase_ew_yellow
            )
            traci.trafficlight.setPhase(self.sim_cfg.tls_id, yellow_phase)

            # Step yellow interval
            for _ in range(self.rl_cfg.yellow_duration):
                traci.simulationStep()
                self.current_sim_time += 1

            # Switch to new green phase
            traci.trafficlight.setPhase(self.sim_cfg.tls_id, target_tls_phase)
            self.current_green_phase = desired_green
            self.current_tls_phase = target_tls_phase
            self.phase_elapsed_time = 0
        else:
            self.phase_elapsed_time += self.rl_cfg.decision_interval

        # Advance simulation for decision interval
        departed_count = 0
        arrived_count = 0
        interval_steps = self.rl_cfg.decision_interval

        for _ in range(interval_steps):
            traci.simulationStep()
            self.current_sim_time += 1
            departed_count += len(traci.simulation.getDepartedIDList())
            arrived_count += len(traci.simulation.getArrivedIDList())

        # Measure current state
        total_queue = 0
        total_wait = 0.0
        waits_by_corridor = {"NS": 0.0, "EW": 0.0}

        for arm in ("N", "S", "E", "W"):
            edge_id = f"{arm}_to_J0"
            try:
                q = traci.edge.getLastStepHaltingNumber(edge_id)
                w = traci.edge.getWaitingTime(edge_id)
            except Exception:
                q, w = 0, 0.0
            total_queue += q
            total_wait += w
            corridor = "NS" if arm in ("N", "S") else "EW"
            waits_by_corridor[corridor] += w

        # Calculate reward
        wait_diff = total_wait - self.prev_total_wait
        self.prev_total_wait = total_wait

        fairness_penalty = abs(waits_by_corridor["NS"] - waits_by_corridor["EW"]) / 60.0

        reward = (
            - self.rl_cfg.w_wait * (total_wait / 30.0)
            - self.rl_cfg.w_queue * total_queue
            + self.rl_cfg.w_throughput * arrived_count
            - self.rl_cfg.w_fairness * fairness_penalty
        )

        # Scale reward to well-conditioned range ~ [-5, 5]
        reward = float(np.clip(reward, -10.0, 5.0))

        terminated = self.current_sim_time >= self.sim_duration
        truncated = False

        obs = self._get_obs()
        info = {
            "time": self.current_sim_time,
            "total_queue": total_queue,
            "total_wait": total_wait,
            "arrived": arrived_count,
        }

        if terminated:
            close_traci_safely()

        return obs, reward, terminated, truncated, info

    def close(self) -> None:
        """Close environment and cleanup TraCI."""
        close_traci_safely()
