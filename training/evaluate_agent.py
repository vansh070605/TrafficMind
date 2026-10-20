"""Evaluation script for trained RL agent against Fixed-Time and Adaptive baselines."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from controllers.adaptive import AdaptiveController
from controllers.fixed_time import FixedTimeController
from controllers.rl_controller import RLTrafficController
from simulation.runner import run_simulation


def evaluate_agent(
    model_path: Path,
    scenario: str = "normal",
    duration: int = 300,
    seed: int = 42,
    gui: bool = False,
) -> None:
    """Run head-to-head comparison between Fixed-Time, Adaptive, and trained RL agent."""
    print("=" * 70)
    print("TRAFFIC CHAOS SIMULATOR — HEAD-TO-HEAD CONTROLLER EVALUATION")
    print(f"Scenario: {scenario} | Duration: {duration}s | Seed: {seed} | GUI: {gui}")
    print("=" * 70)

    # 1. Baseline: Fixed-Time
    print("\n[1/3] Running Fixed-Time Baseline...")
    fixed_ctrl = FixedTimeController()
    sum_fixed, _ = run_simulation(
        controller=fixed_ctrl,
        scenario=scenario,
        duration=duration,
        seed=seed,
        gui=gui,
    )

    # 2. Baseline: Adaptive
    print("[2/3] Running Adaptive Baseline...")
    adapt_ctrl = AdaptiveController()
    sum_adapt, _ = run_simulation(
        controller=adapt_ctrl,
        scenario=scenario,
        duration=duration,
        seed=seed,
        gui=gui,
    )

    # 3. RL Agent
    print(f"[3/3] Running RL Agent ({model_path.name})...")
    rl_ctrl = RLTrafficController(model_path=model_path)
    sum_rl, _ = run_simulation(
        controller=rl_ctrl,
        scenario=scenario,
        duration=duration,
        seed=seed,
        gui=gui,
    )

    # Display Side-by-Side Comparison Table
    print("\n" + "=" * 76)
    print(f"{'METRIC':<28} | {'FIXED-TIME':<13} | {'ADAPTIVE':<13} | {'RL (PPO)':<13}")
    print("-" * 76)

    metrics_to_show = [
        ("Completed Vehicles", "completed_vehicles", "{:d}"),
        ("Throughput (veh/min)", "throughput_per_minute", "{:.2f}"),
        ("Avg Waiting Time (s)", "avg_waiting_time_sec", "{:.2f}"),
        ("Max Waiting Time (s)", "max_waiting_time_sec", "{:.2f}"),
        ("Avg Queue Length", "avg_queue_length", "{:.2f}"),
        ("Max Queue Length", "max_queue_length", "{:d}"),
        ("Avg Trip Duration (s)", "avg_trip_duration_sec", "{:.2f}"),
        ("Avg Stops per Vehicle", "avg_stops_per_vehicle", "{:.2f}"),
        ("Simulation Runtime (s)", "wall_clock_time_sec", "{:.3f}"),
    ]

    for label, key, fmt in metrics_to_show:
        val_f = fmt.format(sum_fixed.get(key, 0))
        val_a = fmt.format(sum_adapt.get(key, 0))
        val_r = fmt.format(sum_rl.get(key, 0))
        print(f"{label:<28} | {val_f:<13} | {val_a:<13} | {val_r:<13}")
    print("=" * 76)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained RL agent vs baselines")
    parser.add_argument(
        "--model-path",
        type=str,
        default="outputs/models/ppo_traffic_final.zip",
        help="Path to trained model .zip",
    )
    parser.add_argument("--scenario", type=str, default="normal", help="Evaluation scenario")
    parser.add_argument("--duration", type=int, default=300, help="Simulation duration (seconds)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--gui", action="store_true", help="Launch SUMO-GUI for visual evaluation")
    args = parser.parse_args()

    model_p = Path(args.model_path)
    if not model_p.exists():
        print(f"Error: model file not found at {model_p}. Train an agent first with train_agent.py.")
        return

    evaluate_agent(
        model_path=model_p,
        scenario=args.scenario,
        duration=args.duration,
        seed=args.seed,
        gui=args.gui,
    )


if __name__ == "__main__":
    main()
