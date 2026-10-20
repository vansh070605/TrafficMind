"""Unit and API compliance tests for Gymnasium SumoTrafficEnv."""

import numpy as np
import pytest
from stable_baselines3.common.env_checker import check_env

from environment.traffic_env import SumoTrafficEnv


def test_traffic_env_interface():
    """Verify gymnasium interface, observation and action spaces."""
    env = SumoTrafficEnv(scenario="low", sim_duration=40, gui=False, seed=42)
    try:
        obs, info = env.reset(seed=42)
        assert isinstance(obs, np.ndarray)
        assert obs.shape == (14,)
        assert np.all(obs >= 0.0) and np.all(obs <= 1.0), f"Observation out of bounds: {obs}"

        # Step with action 0 (keep/switch to NS)
        next_obs, reward, terminated, truncated, step_info = env.step(0)
        assert next_obs.shape == (14,)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert "total_queue" in step_info

        # Step with action 1 (switch to EW)
        next_obs2, reward2, terminated2, truncated2, step_info2 = env.step(1)
        assert next_obs2.shape == (14,)
    finally:
        env.close()


def test_sb3_env_checker():
    """Verify environment compatibility with Stable-Baselines3."""
    env = SumoTrafficEnv(scenario="low", sim_duration=40, gui=False, seed=42)
    try:
        # check_env checks spaces, types, resets, step returns
        check_env(env, warn=True)
    finally:
        env.close()
