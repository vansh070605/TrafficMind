"""Visualization and Performance Plotting for Traffic Chaos Simulator.

Generates comparative charts, queue time-series, and directional fairness
visualizations across Fixed-Time, Adaptive, and RL controllers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# Clean modern aesthetic styling
PALETTE = {
    "FixedTimeController": "#64748b",  # Slate
    "AdaptiveController": "#0284c7",   # Sky blue
    "RLTrafficController": "#16a34a",  # Emerald green
}
DISPLAY_NAMES = {
    "FixedTimeController": "Fixed-Time",
    "AdaptiveController": "Adaptive (Rule-Based)",
    "RLTrafficController": "RL Agent (PPO)",
}


def plot_controller_comparisons(
    results_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
    scenario_name: str = "normal",
) -> Path:
    """Generate comprehensive bar chart comparing key metrics with error bars (mean +/- std)."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "outputs" / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = [
        ("avg_waiting_time_sec", "Avg Waiting Time (s)", "Lower is better"),
        ("avg_queue_length", "Avg Queue Length (veh)", "Lower is better"),
        ("avg_trip_duration_sec", "Avg Trip Duration (s)", "Lower is better"),
        ("throughput_per_minute", "Throughput (veh/min)", "Higher is better"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    axes = axes.flatten()

    controllers = list(results_df["controller"].unique())
    numeric_cols = [m[0] for m in metrics if m[0] in results_df.columns]
    agg = results_df.groupby("controller")[numeric_cols].agg(["mean", "std"])

    for idx, (col, title, subtitle) in enumerate(metrics):
        ax = axes[idx]
        x_positions = np.arange(len(controllers))

        means = [float(agg[col]["mean"].get(c, 0.0)) for c in controllers]
        stds = [float(agg[col]["std"].get(c, 0.0)) if not np.isnan(agg[col]["std"].get(c, 0.0)) else 0.0 for c in controllers]
        colors = [PALETTE.get(c, "#475569") for c in controllers]
        labels = [DISPLAY_NAMES.get(c, c) for c in controllers]

        bars = ax.bar(
            x_positions,
            means,
            yerr=stds,
            capsize=5,
            color=colors,
            alpha=0.88,
            edgecolor="#1e293b",
            linewidth=1.2,
        )

        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, fontsize=10, fontweight="medium")
        ax.set_title(f"{title}\n({subtitle})", fontsize=11, fontweight="bold", pad=8)
        ax.grid(axis="y", linestyle=":", alpha=0.6)

        # Label value on top of each bar
        for bar, m in zip(bars, means):
            yval = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                yval + 0.05 * (max(means) if max(means) > 0 else 1.0),
                f"{m:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

    fig.suptitle(
        f"Controller Benchmark Comparison — Scenario: {scenario_name.upper()}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout()

    out_file = output_dir / f"benchmark_comparison_{scenario_name}.png"
    plt.savefig(out_file, dpi=160)
    plt.close()
    return out_file


def plot_queue_dynamics(
    step_data: Dict[str, pd.DataFrame],
    output_dir: Optional[Path] = None,
    scenario_name: str = "normal",
) -> Path:
    """Plot time-series evolution of total intersection queue across controllers."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "outputs" / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 6))

    for ctrl_name, df in step_data.items():
        if df.empty or "step" not in df.columns or "total_queue" not in df.columns:
            continue
        color = PALETTE.get(ctrl_name, "#3b82f6")
        label = DISPLAY_NAMES.get(ctrl_name, ctrl_name)
        # Smooth with rolling average
        smoothed = df["total_queue"].rolling(window=10, min_periods=1).mean()
        plt.plot(df["step"], smoothed, label=label, color=color, linewidth=2.0)

    plt.xlabel("Simulation Time (seconds)", fontsize=11)
    plt.ylabel("Total Intersection Queue (vehicles)", fontsize=11)
    plt.title(
        f"Queue Dynamics Over Time (10s Rolling Mean) — {scenario_name.upper()}",
        fontsize=13,
        fontweight="bold",
    )
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(frameon=True, fontsize=10)
    plt.tight_layout()

    out_file = output_dir / f"queue_dynamics_{scenario_name}.png"
    plt.savefig(out_file, dpi=160)
    plt.close()
    return out_file


def plot_directional_fairness(
    results_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
    scenario_name: str = "normal",
) -> Path:
    """Plot directional waiting times to inspect fairness across approaches."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "outputs" / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if directional data exists in results
    arms = ["N", "S", "E", "W"]
    cols = [f"wait_{a}" for a in arms]
    if not all(c in results_df.columns for c in cols):
        return output_dir

    controllers = results_df["controller"].unique()
    x = np.arange(len(arms))
    width = 0.25

    plt.figure(figsize=(10, 6))

    for i, c in enumerate(controllers):
        subset = results_df[results_df["controller"] == c]
        means = [subset[f"wait_{a}"].mean() for a in arms]
        color = PALETTE.get(c, "#475569")
        label = DISPLAY_NAMES.get(c, c)
        plt.bar(x + (i - 1) * width, means, width, label=label, color=color, alpha=0.9, edgecolor="#1e293b")

    plt.xticks(x, [f"{a} Approach" for a in arms], fontsize=11)
    plt.ylabel("Average Waiting Time (seconds)", fontsize=11)
    plt.title(f"Directional Fairness Analysis — {scenario_name.upper()}", fontsize=13, fontweight="bold")
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    plt.legend(frameon=True, fontsize=10)
    plt.tight_layout()

    out_file = output_dir / f"directional_fairness_{scenario_name}.png"
    plt.savefig(out_file, dpi=160)
    plt.close()
    return out_file
