"""Traffic Demand and Route Generation for Traffic Chaos Simulator.

Generates reproducible SUMO route files (.rou.xml) across multiple scenarios:
- low
- normal
- rush_hour
- unbalanced
- surge
- unseen_evaluation
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ScenarioConfig:
    name: str
    description: str
    rates_ns: float  # vehicles/sec per direction for North and South
    rates_ew: float  # vehicles/sec per direction for East and West
    surge_start: Optional[float] = None
    surge_end: Optional[float] = None
    surge_multiplier: float = 1.0


SCENARIOS: dict[str, ScenarioConfig] = {
    "low": ScenarioConfig(
        name="low",
        description="Light traffic evenly distributed across all directions.",
        rates_ns=0.03,
        rates_ew=0.03,
    ),
    "normal": ScenarioConfig(
        name="normal",
        description="Moderate balanced urban traffic demand.",
        rates_ns=0.075,
        rates_ew=0.075,
    ),
    "rush_hour": ScenarioConfig(
        name="rush_hour",
        description="Heavy balanced peak-hour congestion.",
        rates_ns=0.15,
        rates_ew=0.15,
    ),
    "unbalanced": ScenarioConfig(
        name="unbalanced",
        description="High demand on North-South corridor, light on East-West.",
        rates_ns=0.16,
        rates_ew=0.03,
    ),
    "surge": ScenarioConfig(
        name="surge",
        description="Sudden surge of traffic between t=150s and t=450s.",
        rates_ns=0.05,
        rates_ew=0.05,
        surge_start=150.0,
        surge_end=450.0,
        surge_multiplier=3.2,
    ),
    "unseen_evaluation": ScenarioConfig(
        name="unseen_evaluation",
        description="Novel asymmetric pattern: heavy West-to-East with oscillating cross-traffic.",
        rates_ns=0.04,
        rates_ew=0.14,
    ),
}

# Standard turning probability distributions: 60% straight, 20% left, 20% right
TURN_PROBABILITIES = {"through": 0.60, "left": 0.20, "right": 0.20}


def generate_demand(
    scenario: str = "normal",
    duration: int = 1000,
    seed: int = 42,
    output_path: Optional[Path] = None,
    custom_config: Optional[ScenarioConfig] = None,
) -> Path:
    """Generate SUMO route file for the specified scenario and random seed.

    Args:
        scenario: Name of predefined scenario or 'custom'.
        duration: Total simulation time in seconds.
        seed: Random seed for reproducibility.
        output_path: Filepath where the .rou.xml should be saved.
        custom_config: Custom ScenarioConfig if scenario == 'custom'.

    Returns:
        Path to generated .rou.xml file.
    """
    if custom_config:
        cfg = custom_config
    elif scenario in SCENARIOS:
        cfg = SCENARIOS[scenario]
    else:
        raise ValueError(f"Unknown scenario '{scenario}'. Available: {list(SCENARIOS.keys())}")

    if output_path is None:
        scenarios_dir = Path(__file__).resolve().parent / "scenarios"
        scenarios_dir.mkdir(parents=True, exist_ok=True)
        output_path = scenarios_dir / f"{scenario}_seed{seed}.rou.xml"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)

    # Routes per origin
    routes = {
        "N": [
            ("r_N_S", "N_to_J0 J0_to_S", TURN_PROBABILITIES["through"]),
            ("r_N_E", "N_to_J0 J0_to_E", TURN_PROBABILITIES["left"]),
            ("r_N_W", "N_to_J0 J0_to_W", TURN_PROBABILITIES["right"]),
        ],
        "S": [
            ("r_S_N", "S_to_J0 J0_to_N", TURN_PROBABILITIES["through"]),
            ("r_S_W", "S_to_J0 J0_to_W", TURN_PROBABILITIES["left"]),
            ("r_S_E", "S_to_J0 J0_to_E", TURN_PROBABILITIES["right"]),
        ],
        "E": [
            ("r_E_W", "E_to_J0 J0_to_W", TURN_PROBABILITIES["through"]),
            ("r_E_S", "E_to_J0 J0_to_S", TURN_PROBABILITIES["left"]),
            ("r_E_N", "E_to_J0 J0_to_N", TURN_PROBABILITIES["right"]),
        ],
        "W": [
            ("r_W_E", "W_to_J0 J0_to_E", TURN_PROBABILITIES["through"]),
            ("r_W_N", "W_to_J0 J0_to_N", TURN_PROBABILITIES["left"]),
            ("r_W_S", "W_to_J0 J0_to_S", TURN_PROBABILITIES["right"]),
        ],
    }

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">',
        '    <!-- Vehicle Type Definition -->',
        '    <vType id="passenger" accel="2.6" decel="4.5" sigma="0.5" length="5.0" minGap="2.5" maxSpeed="13.89" guiShape="passenger"/>',
        '    <!-- Route Definitions -->',
    ]

    for arm, arm_routes in routes.items():
        for r_id, edges, _ in arm_routes:
            xml_lines.append(f'    <route id="{r_id}" edges="{edges}"/>')

    xml_lines.append('    <!-- Vehicle Flows / Trips -->')

    veh_counter = 0

    for step in range(duration):
        is_surge = False
        if cfg.surge_start is not None and cfg.surge_end is not None:
            if cfg.surge_start <= step <= cfg.surge_end:
                is_surge = True

        mult = cfg.surge_multiplier if is_surge else 1.0

        for arm in ("N", "S", "E", "W"):
            base_rate = cfg.rates_ns if arm in ("N", "S") else cfg.rates_ew
            effective_rate = base_rate * mult

            # Bernoulli trial per second
            if rng.random() < effective_rate:
                # Select turning movement based on probability weights
                arm_routes = routes[arm]
                r_choice = rng.choices(
                    [r[0] for r in arm_routes],
                    weights=[r[2] for r in arm_routes],
                    k=1,
                )[0]

                xml_lines.append(
                    f'    <vehicle id="veh_{arm}_{veh_counter}" type="passenger" route="{r_choice}" depart="{step}.00" departLane="best" departSpeed="max"/>'
                )
                veh_counter += 1

    xml_lines.append('</routes>')

    output_path.write_text("\n".join(xml_lines), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    out = generate_demand("normal", duration=300, seed=42)
    print(f"Generated route file at: {out}")
