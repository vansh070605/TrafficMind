"""Global configuration for Traffic Chaos Simulator."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SimulationConfig:
    network_dir: Path = Path(__file__).resolve().parent.parent / "simulation" / "network"
    scenarios_dir: Path = Path(__file__).resolve().parent.parent / "simulation" / "scenarios"
    net_file: Path = network_dir / "intersection.net.xml"
    sumo_cfg: Path = network_dir / "intersection.sumocfg"
    
    arm_length: float = 250.0
    num_lanes: int = 2
    speed_limit: float = 13.89  # m/s (~50 km/h)

    # Signal Phase Indices:
    # Phase 0: NS Green
    # Phase 1: NS Yellow
    # Phase 2: EW Green
    # Phase 3: EW Yellow
    tls_id: str = "J0"
    yellow_duration: int = 3
    min_green: int = 10
    max_green: int = 60
    fixed_green: int = 35

    # Safe phases
    phase_ns_green: int = 0
    phase_ns_yellow: int = 1
    phase_ew_green: int = 2
    phase_ew_yellow: int = 3

    # Incoming edges to junction J0
    incoming_edges: list[str] = field(default_factory=lambda: [
        "N_to_J0", "S_to_J0", "E_to_J0", "W_to_J0"
    ])
    outgoing_edges: list[str] = field(default_factory=lambda: [
        "J0_to_N", "J0_to_S", "J0_to_E", "J0_to_W"
    ])


@dataclass
class AdaptiveConfig:
    min_green: int = 10
    max_green: int = 60
    yellow_time: int = 3
    starvation_threshold_sec: float = 40.0
    queue_weight: float = 1.0
    wait_time_weight: float = 0.5


@dataclass
class RLConfig:
    decision_interval: int = 5  # Actions taken every 5 simulation seconds
    min_green_before_switch: int = 10
    yellow_duration: int = 3
    max_steps_per_episode: int = 1000
    
    # Reward formulation weights:
    # reward = - w_wait * mean_waiting_time - w_queue * total_queue - w_stop * new_stops + w_throughput * departed_this_step
    w_wait: float = 0.5
    w_queue: float = 0.25
    w_stop: float = 0.1
    w_throughput: float = 1.0
    w_fairness: float = 0.2  # penalizes extreme variance between NS and EW wait times


DEFAULT_SIM_CONFIG = SimulationConfig()
DEFAULT_ADAPTIVE_CONFIG = AdaptiveConfig()
DEFAULT_RL_CONFIG = RLConfig()
