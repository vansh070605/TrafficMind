"""RL Agent Training Script for Traffic Chaos Simulator.

Trains a PPO policy on SumoTrafficEnv, records episode rewards, saves
model checkpoints, and plots training progress curves.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

from configs.default_config import DEFAULT_RL_CONFIG, DEFAULT_SIM_CONFIG
from environment.traffic_env import SumoTrafficEnv


class TrainingProgressCallback(BaseCallback):
    """Logs episode reward statistics and tracks training curves."""

    def __init__(self, log_dir: Path, verbose: int = 1) -> None:
        super().__init__(verbose)
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.episode_rewards: List[float] = []
        self.episode_lengths: List[int] = []
        self.current_reward = 0.0
        self.current_length = 0

    def _on_step(self) -> bool:
        rewards = self.locals.get("rewards", [0.0])
        dones = self.locals.get("dones", [False])

        self.current_reward += float(rewards[0])
        self.current_length += 1

        if dones[0]:
            self.episode_rewards.append(self.current_reward)
            self.episode_lengths.append(self.current_length)
            if self.verbose > 0:
                print(
                    f"Episode {len(self.episode_rewards)}: "
                    f"Total Reward = {self.current_reward:.2f}, "
                    f"Length = {self.current_length} steps"
                )
            self.current_reward = 0.0
            self.current_length = 0

        return True

    def save_log_and_plot(self) -> Path:
        """Export reward history to CSV and plot training curve."""
        df = pd.DataFrame({
            "episode": list(range(1, len(self.episode_rewards) + 1)),
            "reward": self.episode_rewards,
            "length": self.episode_lengths,
        })
        csv_path = self.log_dir / "training_rewards.csv"
        df.to_csv(csv_path, index=False)

        if len(self.episode_rewards) > 0:
            plt.figure(figsize=(9, 5))
            plt.plot(df["episode"], df["reward"], marker="o", color="#2563eb", label="Episode Reward")
            if len(df["reward"]) >= 5:
                rolling_avg = df["reward"].rolling(window=min(5, len(df["reward"])), min_periods=1).mean()
                plt.plot(df["episode"], rolling_avg, color="#dc2626", linestyle="--", label="Rolling Avg (5)")
            plt.xlabel("Episode", fontsize=11)
            plt.ylabel("Cumulative Reward", fontsize=11)
            plt.title("PPO Agent Training Reward Curve", fontsize=13, fontweight="bold")
            plt.grid(True, linestyle=":", alpha=0.6)
            plt.legend()
            plt.tight_layout()

            plot_path = self.log_dir / "training_curve.png"
            plt.savefig(plot_path, dpi=150)
            plt.close()
            return plot_path

        return csv_path


def train_agent(
    scenario: str = "normal",
    total_timesteps: int = 5000,
    seed: int = 42,
    sim_duration: int = 500,
    output_dir: Optional[Path] = None,
) -> Path:
    """Train a PPO policy on SumoTrafficEnv and save model checkpoint."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "outputs"
    models_dir = output_dir / "models"
    plots_dir = output_dir / "plots"
    logs_dir = output_dir / "logs"

    models_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating training environment: scenario={scenario}, duration={sim_duration}s, seed={seed}")
    env = SumoTrafficEnv(
        scenario=scenario,
        sim_duration=sim_duration,
        gui=False,
        seed=seed,
    )

    callback = TrainingProgressCallback(log_dir=logs_dir, verbose=1)

    print(f"Initializing PPO agent with {total_timesteps} total timesteps...")
    model = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=3e-4,
        n_steps=128,
        batch_size=32,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=0,
        seed=seed,
    )

    try:
        model.learn(total_timesteps=total_timesteps, callback=callback)
    finally:
        env.close()

    final_model_path = models_dir / "ppo_traffic_final.zip"
    model.save(str(final_model_path))
    print(f"Model saved successfully to: {final_model_path}")

    curve_path = callback.save_log_and_plot()
    print(f"Training history saved: {curve_path}")

    return final_model_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PPO traffic signal controller")
    parser.add_argument("--timesteps", type=int, default=2000, help="Total training timesteps")
    parser.add_argument("--scenario", type=str, default="normal", help="Training scenario")
    parser.add_argument("--duration", type=int, default=400, help="Simulation duration per episode")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    train_agent(
        scenario=args.scenario,
        total_timesteps=args.timesteps,
        seed=args.seed,
        sim_duration=args.duration,
    )


if __name__ == "__main__":
    main()
