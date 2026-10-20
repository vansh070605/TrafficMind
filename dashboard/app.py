"""Interactive Streamlit Dashboard for Traffic Chaos Simulator.

Enables interactive scenario configuration, live simulation triggers (GUI or headless),
head-to-head controller benchmarking, reward curve inspection, and CSV result downloads.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from controllers.adaptive import AdaptiveController
from controllers.fixed_time import FixedTimeController
from controllers.rl_controller import RLTrafficController
from evaluation.plots import (
    plot_controller_comparisons,
    plot_directional_fairness,
    plot_queue_dynamics,
)
from simulation.generate_demand import SCENARIOS
from simulation.runner import run_simulation
from simulation.sumo_utils import close_traci_safely, find_sumo_home

# Page configuration
st.set_page_config(
    page_title="Traffic Chaos Simulator",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling for premium look
st.markdown("""
<style>
    .metric-card {
        background-color: #1e293b;
        color: white;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid #38bdf8;
    }
    .metric-label { font-size: 0.85rem; color: #94a3b8; margin-bottom: 4px; }
    .metric-val { font-size: 1.6rem; font-weight: bold; color: #f8fafc; }
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


def main() -> None:
    st.title("🚦 Traffic Chaos Simulator")
    st.markdown(
        "**Adaptive AI Traffic Control** — Benchmarking Fixed-Time, Queue-Adaptive, "
        "and Deep Reinforcement Learning (PPO) signal controllers on microscopic SUMO simulations."
    )

    # Check SUMO
    sumo_home = find_sumo_home()
    if sumo_home is None:
        st.error("⚠️ SUMO installation not detected! Please ensure SUMO is installed on your system.")

    # Sidebar controls
    st.sidebar.header("🛠️ Simulation Setup")

    scenario_name = st.sidebar.selectbox(
        "Traffic Scenario",
        options=list(SCENARIOS.keys()),
        index=1,
        help="Select spatial & temporal demand pattern.",
    )
    st.sidebar.caption(f"_{SCENARIOS[scenario_name].description}_")

    controller_choice = st.sidebar.selectbox(
        "Traffic Signal Controller",
        options=["Fixed-Time", "Adaptive (Rule-Based)", "RL Agent (PPO)"],
        index=1,
    )

    duration = st.sidebar.slider("Simulation Duration (seconds)", min_value=30, max_value=600, value=120, step=30)
    seed = st.sidebar.number_input("Random Seed", min_value=1, max_value=9999, value=42, step=1)
    launch_gui = st.sidebar.checkbox("Launch Visual SUMO-GUI Window", value=False, help="Opens real-time microscopic SUMO-GUI window during run.")

    model_path = PROJECT_ROOT / "outputs" / "models" / "ppo_traffic_final.zip"
    rl_available = model_path.exists()

    if controller_choice == "RL Agent (PPO)" and not rl_available:
        st.sidebar.warning("⚠️ No trained model found at `outputs/models/ppo_traffic_final.zip`. Run training first!")

    # Tabs
    tab_single, tab_compare, tab_rl, tab_data = st.tabs([
        "🚀 Run Controller",
        "⚖️ Head-to-Head Comparison",
        "🧠 RL Training & Curves",
        "📂 Benchmark Data & Plots",
    ])

    # ---------------- TAB 1: SINGLE CONTROLLER RUN ----------------
    with tab_single:
        st.subheader("Single Controller Simulation")

        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            run_btn = st.button("▶️ Start Simulation", type="primary", use_container_width=True)

        if run_btn:
            close_traci_safely()

            ctrl_instance = None
            if controller_choice == "Fixed-Time":
                ctrl_instance = FixedTimeController()
            elif controller_choice == "Adaptive (Rule-Based)":
                ctrl_instance = AdaptiveController()
            elif controller_choice == "RL Agent (PPO)":
                if not rl_available:
                    st.error("Cannot run RL controller: model checkpoint not found.")
                    return
                ctrl_instance = RLTrafficController(model_path=model_path)

            with st.spinner(f"Simulating {controller_choice} on {scenario_name} ({duration}s)..."):
                try:
                    summary, step_df = run_simulation(
                        controller=ctrl_instance,
                        scenario=scenario_name,
                        duration=duration,
                        seed=seed,
                        gui=launch_gui,
                    )
                    st.session_state["last_summary"] = summary
                    st.session_state["last_step_df"] = step_df
                    st.session_state["last_ctrl"] = controller_choice
                    st.session_state["last_sc"] = scenario_name
                    st.success("Simulation completed successfully!")
                except Exception as e:
                    st.error(f"Simulation failed: {e}")
                finally:
                    close_traci_safely()

        if "last_summary" in st.session_state:
            s = st.session_state["last_summary"]
            df = st.session_state["last_step_df"]

            st.write(f"**Results for {st.session_state['last_ctrl']} on '{st.session_state['last_sc']}' scenario:**")

            # KPI metrics cards
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            with kpi1:
                st.metric("Avg Waiting Time", f"{s['avg_waiting_time_sec']:.2f} s")
            with kpi2:
                st.metric("Avg Queue Length", f"{s['avg_queue_length']:.2f} veh")
            with kpi3:
                st.metric("Max Waiting Time", f"{s['max_waiting_time_sec']:.1f} s")
            with kpi4:
                st.metric("Throughput", f"{s['throughput_per_minute']:.1f} /min")
            with kpi5:
                st.metric("Completed Trips", f"{s['completed_vehicles']} / {s['total_vehicles_departed']}")

            # Time-series charts
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.markdown("##### Total Intersection Queue Over Time")
                if not df.empty and "total_queue" in df.columns:
                    st.line_chart(df.set_index("step")[["total_queue"]])

            with col_chart2:
                st.markdown("##### Directional Queues (N, S, E, W)")
                if not df.empty and "queue_N" in df.columns:
                    st.line_chart(df.set_index("step")[["queue_N", "queue_S", "queue_E", "queue_W"]])

            # Directional performance breakdown table
            st.markdown("##### Directional Performance Breakdown")
            dir_data = s.get("directional", {})
            if dir_data:
                dir_df = pd.DataFrame(dir_data).T
                dir_df.columns = ["Completed Trips", "Avg Duration (s)", "Avg Waiting Time (s)", "Avg Stops"]
                st.dataframe(dir_df, use_container_width=True)

    # ---------------- TAB 2: HEAD-TO-HEAD COMPARISON ----------------
    with tab_compare:
        st.subheader("Head-to-Head Controller Benchmark")
        st.write("Compare Fixed-Time, Adaptive, and RL (PPO) on equivalent demand and seed.")

        if st.button("⚡ Run Full 3-Way Comparison", type="secondary"):
            close_traci_safely()
            controllers = [
                ("Fixed-Time", FixedTimeController()),
                ("Adaptive", AdaptiveController()),
            ]
            if rl_available:
                controllers.append(("RL (PPO)", RLTrafficController(model_path=model_path)))

            results = []
            step_dfs = {}

            progress_bar = st.progress(0.0)
            status_text = st.empty()

            for i, (name, ctrl) in enumerate(controllers):
                status_text.text(f"Running controller {name}...")
                sum_res, df_res = run_simulation(
                    controller=ctrl,
                    scenario=scenario_name,
                    duration=duration,
                    seed=seed,
                    gui=False,
                )
                sum_res["Controller"] = name
                results.append(sum_res)
                step_dfs[name] = df_res
                progress_bar.progress((i + 1) / len(controllers))

            progress_bar.empty()
            status_text.empty()
            st.session_state["comp_results"] = results
            st.session_state["comp_dfs"] = step_dfs

        if "comp_results" in st.session_state:
            comp_list = st.session_state["comp_results"]
            comp_df = pd.DataFrame(comp_list)

            display_cols = [
                "Controller",
                "avg_waiting_time_sec",
                "max_waiting_time_sec",
                "avg_queue_length",
                "throughput_per_minute",
                "avg_trip_duration_sec",
                "completed_vehicles",
                "wall_clock_time_sec",
            ]
            rename_map = {
                "avg_waiting_time_sec": "Avg Wait (s)",
                "max_waiting_time_sec": "Max Wait (s)",
                "avg_queue_length": "Avg Queue",
                "throughput_per_minute": "Throughput (/min)",
                "avg_trip_duration_sec": "Avg Duration (s)",
                "completed_vehicles": "Completed Trips",
                "wall_clock_time_sec": "Runtime (s)",
            }
            styled_df = comp_df[display_cols].rename(columns=rename_map)
            st.dataframe(styled_df, use_container_width=True)

            # Comparative Bar Charts
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### Average Waiting Time (s) — Lower is better")
                chart_data = comp_df[["Controller", "avg_waiting_time_sec"]].set_index("Controller")
                st.bar_chart(chart_data)

            with c2:
                st.markdown("##### Average Queue Length — Lower is better")
                chart_data2 = comp_df[["Controller", "avg_queue_length"]].set_index("Controller")
                st.bar_chart(chart_data2)

    # ---------------- TAB 3: RL TRAINING ----------------
    with tab_rl:
        st.subheader("Reinforcement Learning Agent Inspection")

        curve_path = PROJECT_ROOT / "outputs" / "logs" / "training_curve.png"
        rewards_csv = PROJECT_ROOT / "outputs" / "logs" / "training_rewards.csv"

        if curve_path.exists():
            st.markdown("##### PPO Training Convergence Curve")
            st.image(str(curve_path), use_column_width=True)

        if rewards_csv.exists():
            st.markdown("##### Episode Reward Logs")
            rew_df = pd.read_csv(rewards_csv)
            st.dataframe(rew_df, use_container_width=True)

        st.markdown("---")
        st.markdown("##### Retrain RL Agent")
        st.write("Train a new PPO agent directly from the dashboard.")
        c_ts, c_ep_len, c_train_btn = st.columns([1, 1, 1])
        with c_ts:
            timesteps = st.number_input("Timesteps", min_value=500, max_value=20000, value=2000, step=500)
        with c_ep_len:
            train_sc = st.selectbox("Training Scenario", options=list(SCENARIOS.keys()), index=1)
        with c_train_btn:
            st.write("")
            st.write("")
            start_train = st.button("🚀 Train Agent Now")

        if start_train:
            from training.train_agent import train_agent
            close_traci_safely()
            with st.spinner(f"Training PPO agent for {timesteps} timesteps on {train_sc}..."):
                try:
                    new_model = train_agent(
                        scenario=train_sc,
                        total_timesteps=timesteps,
                        seed=seed,
                        sim_duration=duration,
                    )
                    st.success(f"Agent training finished! Model saved to {new_model}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Training failed: {e}")
                finally:
                    close_traci_safely()

    # ---------------- TAB 4: DATA & PLOTS ----------------
    with tab_data:
        st.subheader("Exported Benchmark Datasets and Visualizations")

        csv_summary = PROJECT_ROOT / "outputs" / "csv" / "benchmark_summary.csv"
        csv_results = PROJECT_ROOT / "outputs" / "csv" / "benchmark_results.csv"

        if csv_summary.exists():
            st.markdown("##### Multi-Scenario Benchmark Aggregated Summary")
            sum_df = pd.read_csv(csv_summary, header=[0, 1], index_col=[0, 1])
            st.dataframe(sum_df, use_container_width=True)

        if csv_results.exists():
            st.markdown("##### Detailed Simulation Runs Log")
            res_df = pd.read_csv(csv_results)
            st.dataframe(res_df.head(20), use_container_width=True)

            csv_bytes = res_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download benchmark_results.csv",
                data=csv_bytes,
                file_name="benchmark_results.csv",
                mime="text/csv",
            )

        # Show gallery of saved plots
        st.markdown("##### Generated Benchmark Figures")
        plots_dir = PROJECT_ROOT / "outputs" / "plots"
        if plots_dir.exists():
            plot_files = list(plots_dir.glob("*.png"))
            if plot_files:
                cols = st.columns(2)
                for idx, pf in enumerate(plot_files):
                    with cols[idx % 2]:
                        st.image(str(pf), caption=pf.name, use_column_width=True)


if __name__ == "__main__":
    main()
