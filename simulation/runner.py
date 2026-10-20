"""Simulation Runner for Traffic Chaos Simulator.

Coordinates SUMO/SUMO-GUI execution, TraCI interaction, signal controller
interfacing, and metric recording.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from simulation.sumo_utils import (
    close_traci_safely,
    get_sumo_binary,
    setup_sumo_environment,
)

# Configure SUMO_HOME and sys.path for SUMO tools before importing traci
setup_sumo_environment()
import traci

from configs.default_config import DEFAULT_SIM_CONFIG, SimulationConfig
from controllers.base_controller import BaseTrafficController
from evaluation.metrics import MetricsCollector
from simulation.generate_demand import generate_demand
from simulation.generate_network import generate_network


def get_traffic_state(tls_id: str, incoming_edges: list[str]) -> Dict[str, Any]:
    """Inspect current simulation state through TraCI and return normalized features."""
    current_phase = traci.trafficlight.getPhase(tls_id)

    queues_by_arm: Dict[str, int] = {"N": 0, "S": 0, "E": 0, "W": 0}
    waits_by_arm: Dict[str, float] = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
    counts_by_arm: Dict[str, int] = {"N": 0, "S": 0, "E": 0, "W": 0}
    edge_data: Dict[str, Dict[str, Any]] = {}

    max_wait = 0.0

    for edge_id in incoming_edges:
        arm = edge_id.split("_")[0]  # 'N', 'S', 'E', or 'W'
        edge_queue = traci.edge.getLastStepHaltingNumber(edge_id)
        edge_wait = traci.edge.getWaitingTime(edge_id)
        edge_count = traci.edge.getLastStepVehicleNumber(edge_id)

        queues_by_arm[arm] += edge_queue
        waits_by_arm[arm] += edge_wait
        counts_by_arm[arm] += edge_count

        edge_data[edge_id] = {
            "queue": edge_queue,
            "waiting_time": edge_wait,
            "vehicle_count": edge_count,
        }

    # Find max individual vehicle waiting time on incoming edges
    active_vehicles = traci.vehicle.getIDList()
    for vid in active_vehicles:
        try:
            wait = traci.vehicle.getAccumulatedWaitingTime(vid)
            if wait > max_wait:
                max_wait = wait
        except Exception:
            pass

    return {
        "current_phase": current_phase,
        "queues": queues_by_arm,
        "waiting_times": waits_by_arm,
        "vehicle_counts": counts_by_arm,
        "max_waiting_time": max_wait,
        "edge_data": edge_data,
        "active_vehicle_ids": list(active_vehicles),
    }


def run_simulation(
    controller: Optional[BaseTrafficController] = None,
    scenario: str = "normal",
    duration: int = 1000,
    seed: int = 42,
    gui: bool = False,
    config: SimulationConfig = DEFAULT_SIM_CONFIG,
    step_delay_ms: int = 0,
) -> Tuple[Dict[str, Any], Any]:
    """Execute a complete simulation run.

    Args:
        controller: Signal controller instance (FixedTime, Adaptive, etc.).
                    If None, SUMO's internal default static program is used.
        scenario: Demand scenario name.
        duration: Duration in simulation seconds.
        seed: Random seed for demand and simulation.
        gui: Whether to launch sumo-gui for visual simulation.
        config: SimulationConfig instance.
        step_delay_ms: GUI delay in milliseconds per step (for visual pacing).

    Returns:
        (summary_metrics_dict, step_dataframe)
    """
    setup_sumo_environment()
    close_traci_safely()

    # 1. Ensure network file exists
    net_file = config.net_file
    if not net_file.exists():
        net_file = generate_network(output_dir=config.network_dir, arm_length=config.arm_length)

    # 2. Generate scenario demand file
    route_file = generate_demand(
        scenario=scenario,
        duration=duration,
        seed=seed,
        output_path=config.scenarios_dir / f"{scenario}_seed{seed}.rou.xml",
    )

    # 3. Resolve executable
    sumo_bin = get_sumo_binary(gui=gui)

    sumo_cmd = [
        sumo_bin,
        "-n", str(net_file),
        "-r", str(route_file),
        "--step-length", "1.0",
        "--time-to-teleport", "-1",
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--seed", str(seed),
    ]

    if gui:
        view_settings = config.network_dir / "viewsettings.xml"
        if view_settings.exists():
            sumo_cmd.extend(["--gui-settings-file", str(view_settings)])
        sumo_cmd.extend(["--start", "true", "--quit-on-end", "true"])
        if step_delay_ms > 0:
            sumo_cmd.extend(["--delay", str(step_delay_ms)])

    collector = MetricsCollector(sim_duration=duration)
    collector.start()

    if controller:
        controller.reset()

    try:
        traci.start(sumo_cmd)
        tls_id = config.tls_id

        current_phase = traci.trafficlight.getPhase(tls_id)
        phase_duration = 0

        for step in range(duration):
            # Fetch state before step
            state = get_traffic_state(tls_id, config.incoming_edges)
            state["phase_duration"] = phase_duration

            # Let controller decide next phase
            if controller is not None:
                desired_phase = controller.step(current_time=step, state=state)
                if desired_phase != current_phase:
                    traci.trafficlight.setPhase(tls_id, desired_phase)
                    current_phase = desired_phase
                    phase_duration = 0
                else:
                    phase_duration += 1
            else:
                # SUMO default controller
                new_phase = traci.trafficlight.getPhase(tls_id)
                if new_phase != current_phase:
                    current_phase = new_phase
                    phase_duration = 0
                else:
                    phase_duration += 1

            # Advance simulation 1 second
            traci.simulationStep()

            departed = traci.simulation.getDepartedIDList()
            arrived = traci.simulation.getArrivedIDList()
            active = traci.vehicle.getIDList()

            collector.record_step(
                current_time=step,
                current_phase=current_phase,
                queues_by_arm=state["queues"],
                waits_by_arm=state["waiting_times"],
                counts_by_arm=state["vehicle_counts"],
                active_veh_ids=list(active),
                departed_veh_ids=list(departed),
                arrived_veh_ids=list(arrived),
                traci_client=traci,
            )

            if step_delay_ms > 0 and gui:
                time.sleep(step_delay_ms / 1000.0)

    finally:
        collector.finish()
        close_traci_safely()

    summary = collector.get_summary()
    step_df = collector.get_step_dataframe()
    return summary, step_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Traffic Chaos Simulator Runner")
    parser.add_argument(
        "--controller",
        type=str,
        default="fixed",
        choices=["fixed", "adaptive", "rl", "none"],
        help="Controller type to run",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="outputs/models/ppo_traffic_final.zip",
        help="Path to trained RL model checkpoint (used if controller=rl)",
    )
    parser.add_argument("--scenario", type=str, default="normal", help="Traffic scenario name")
    parser.add_argument("--duration", type=int, default=300, help="Simulation duration (seconds)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--gui", action="store_true", help="Launch SUMO-GUI visualizer")
    parser.add_argument("--delay", type=int, default=50, help="GUI delay ms per step")
    args = parser.parse_args()

    controller = None
    if args.controller == "fixed":
        from controllers.fixed_time import FixedTimeController
        controller = FixedTimeController()
    elif args.controller == "adaptive":
        from controllers.adaptive import AdaptiveController
        controller = AdaptiveController()
    elif args.controller == "rl":
        from controllers.rl_controller import RLTrafficController
        controller = RLTrafficController(model_path=args.model_path)

    ctrl_name = controller.name if controller else "SUMO Default Static"
    print(f"Starting simulation: controller={ctrl_name}, scenario={args.scenario}, duration={args.duration}s, seed={args.seed}, gui={args.gui}")

    summary, _ = run_simulation(
        controller=controller,
        scenario=args.scenario,
        duration=args.duration,
        seed=args.seed,
        gui=args.gui,
        step_delay_ms=args.delay if args.gui else 0,
    )

    print("\n--- Simulation Summary ---")
    for k, v in summary.items():
        if k != "directional":
            print(f"  {k}: {v}")
    print("Directional performance:")
    for arm, stats in summary.get("directional", {}).items():
        print(f"  {arm}: {stats}")


if __name__ == "__main__":
    main()
