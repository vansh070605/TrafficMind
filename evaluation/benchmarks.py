"""Comprehensive Controller Benchmarking Engine.

Runs Fixed-Time, Adaptive, and RL controllers across multiple traffic
scenarios and random seeds, recording mean and variance metrics, saving
CSV results, and producing comparative performance plots.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from controllers.adaptive import AdaptiveController
from controllers.fixed_time import FixedTimeController
from controllers.rl_controller import RLTrafficController
from evaluation.plots import (
    plot_controller_comparisons,
    plot_directional_fairness,
    plot_queue_dynamics,
)
from simulation.runner import run_simulation


def run_benchmarks(
    scenarios: Optional[List[str]] = None,
    seeds: Optional[List[int]] = None,
    duration: int = 300,
    model_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """Execute complete multi-seed multi-scenario benchmark battery."""
    if scenarios is None:
        scenarios = ["normal", "unbalanced", "rush_hour", "unseen_evaluation"]
    if seeds is None:
        seeds = [42, 101, 202]

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "outputs"
    csv_dir = output_dir / "csv"
    plots_dir = output_dir / "plots"
    csv_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    if model_path is None:
        model_path = output_dir / "models" / "ppo_traffic_final.zip"

    all_records: List[Dict] = []
    step_samples: Dict[str, pd.DataFrame] = {}

    print("=" * 70)
    print("TRAFFIC CHAOS SIMULATOR — CONTROLLER BENCHMARK BATTERY")
    print(f"Scenarios: {scenarios}")
    print(f"Seeds: {seeds} | Duration: {duration}s per run")
    print("=" * 70)

    for sc in scenarios:
        print(f"\n>>> Running Scenario: {sc.upper()} <<<")
        for seed in seeds:
            print(f"  Seed {seed}:")

            # 1. Fixed-Time Controller
            fixed_ctrl = FixedTimeController()
            sum_f, df_f = run_simulation(
                controller=fixed_ctrl,
                scenario=sc,
                duration=duration,
                seed=seed,
                gui=False,
            )
            rec_f = _format_record(sum_f, "FixedTimeController", sc, seed)
            all_records.append(rec_f)
            print(f"    - Fixed-Time: Wait={rec_f['avg_waiting_time_sec']:.2f}s, Queue={rec_f['avg_queue_length']:.2f}, Throughput={rec_f['throughput_per_minute']:.1f}/min")

            # 2. Adaptive Controller
            adapt_ctrl = AdaptiveController()
            sum_a, df_a = run_simulation(
                controller=adapt_ctrl,
                scenario=sc,
                duration=duration,
                seed=seed,
                gui=False,
            )
            rec_a = _format_record(sum_a, "AdaptiveController", sc, seed)
            all_records.append(rec_a)
            print(f"    - Adaptive:   Wait={rec_a['avg_waiting_time_sec']:.2f}s, Queue={rec_a['avg_queue_length']:.2f}, Throughput={rec_a['throughput_per_minute']:.1f}/min")

            # 3. RL Controller (if model checkpoint exists)
            if model_path.exists():
                rl_ctrl = RLTrafficController(model_path=model_path)
                sum_r, df_r = run_simulation(
                    controller=rl_ctrl,
                    scenario=sc,
                    duration=duration,
                    seed=seed,
                    gui=False,
                )
                rec_r = _format_record(sum_r, "RLTrafficController", sc, seed)
                all_records.append(rec_r)
                print(f"    - RL (PPO):   Wait={rec_r['avg_waiting_time_sec']:.2f}s, Queue={rec_r['avg_queue_length']:.2f}, Throughput={rec_r['throughput_per_minute']:.1f}/min")
            else:
                print(f"    - RL (PPO):   Skipped (Model not found at {model_path})")

            # Save representative step history for plotting
            if seed == seeds[0] and sc == "normal":
                step_samples["FixedTimeController"] = df_f
                step_samples["AdaptiveController"] = df_a
                if model_path.exists():
                    step_samples["RLTrafficController"] = df_r

    # Convert to DataFrame
    df_results = pd.DataFrame(all_records)
    csv_file = csv_dir / "benchmark_results.csv"
    df_results.to_csv(csv_file, index=False)
    print(f"\nAll benchmark runs saved to: {csv_file}")

    # Aggregated Summary
    summary_cols = [
        "avg_waiting_time_sec",
        "max_waiting_time_sec",
        "avg_queue_length",
        "avg_trip_duration_sec",
        "throughput_per_minute",
        "avg_stops_per_vehicle",
    ]
    summary_df = df_results.groupby(["scenario", "controller"])[summary_cols].agg(["mean", "std"])
    summary_csv = csv_dir / "benchmark_summary.csv"
    summary_df.to_csv(summary_csv)
    print(f"Aggregated summary saved to: {summary_csv}")

    # Generate Plots
    for sc in scenarios:
        sc_df = df_results[df_results["scenario"] == sc]
        if not sc_df.empty:
            plot_controller_comparisons(sc_df, output_dir=plots_dir, scenario_name=sc)
            plot_directional_fairness(sc_df, output_dir=plots_dir, scenario_name=sc)

    if step_samples:
        plot_queue_dynamics(step_samples, output_dir=plots_dir, scenario_name="normal")

    _print_markdown_table(df_results)
    return df_results


def _format_record(summary: Dict, controller_name: str, scenario: str, seed: int) -> Dict:
    """Format single run summary into flat record."""
    dir_stats = summary.get("directional", {})
    return {
        "scenario": scenario,
        "seed": seed,
        "controller": controller_name,
        "completed_vehicles": summary.get("completed_vehicles", 0),
        "uncompleted_vehicles": summary.get("uncompleted_vehicles", 0),
        "completion_rate": summary.get("completion_rate", 0.0),
        "throughput_per_minute": summary.get("throughput_per_minute", 0.0),
        "avg_trip_duration_sec": summary.get("avg_trip_duration_sec", 0.0),
        "avg_waiting_time_sec": summary.get("avg_waiting_time_sec", 0.0),
        "max_waiting_time_sec": summary.get("max_waiting_time_sec", 0.0),
        "avg_queue_length": summary.get("avg_queue_length", 0.0),
        "max_queue_length": summary.get("max_queue_length", 0),
        "avg_stops_per_vehicle": summary.get("avg_stops_per_vehicle", 0.0),
        "wall_clock_time_sec": summary.get("wall_clock_time_sec", 0.0),
        "wait_N": dir_stats.get("N", {}).get("avg_waiting_time", 0.0),
        "wait_S": dir_stats.get("S", {}).get("avg_waiting_time", 0.0),
        "wait_E": dir_stats.get("E", {}).get("avg_waiting_time", 0.0),
        "wait_W": dir_stats.get("W", {}).get("avg_waiting_time", 0.0),
    }


def _print_markdown_table(df: pd.DataFrame) -> None:
    """Print clean comparison table in console."""
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY RESULTS (Mean ± Std)")
    print("=" * 80)
    grouped = df.groupby(["scenario", "controller"])

    headers = [
        "Scenario", "Controller", "Avg Wait (s)", "Avg Queue", "Throughput (/min)", "Max Wait (s)"
    ]
    row_format = "{:<16} | {:<20} | {:<14} | {:<12} | {:<18} | {:<12}"
    print(row_format.format(*headers))
    print("-" * 80)

    for (sc, ctrl), group in grouped:
        w_m, w_s = group["avg_waiting_time_sec"].mean(), group["avg_waiting_time_sec"].std()
        q_m, q_s = group["avg_queue_length"].mean(), group["avg_queue_length"].std()
        t_m, t_s = group["throughput_per_minute"].mean(), group["throughput_per_minute"].std()
        mw_m = group["max_waiting_time_sec"].mean()

        ctrl_short = ctrl.replace("Controller", "")
        wait_str = f"{w_m:.2f} ± {w_s:.2f}"
        queue_str = f"{q_m:.2f} ± {q_s:.2f}"
        tp_str = f"{t_m:.2f} ± {t_s:.2f}"
        max_str = f"{mw_m:.1f}"

        print(row_format.format(sc, ctrl_short, wait_str, queue_str, tp_str, max_str))
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run complete controller benchmarks")
    parser.add_argument("--duration", type=int, default=200, help="Duration per benchmark run")
    parser.add_argument("--scenarios", nargs="+", default=["normal", "unbalanced", "rush_hour"], help="Scenarios to run")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 101], help="Seeds to evaluate")
    args = parser.parse_args()

    run_benchmarks(
        scenarios=args.scenarios,
        seeds=args.seeds,
        duration=args.duration,
    )
