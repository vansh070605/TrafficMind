"""Unit and integration tests for network generation and simulation foundation."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from configs.default_config import DEFAULT_SIM_CONFIG
from simulation.generate_demand import SCENARIOS, generate_demand
from simulation.generate_network import generate_network
from simulation.runner import run_simulation
from simulation.sumo_utils import find_sumo_home, get_netconvert_binary, get_sumo_binary


def test_sumo_binaries_present():
    """Verify SUMO executables are discovered."""
    sumo_home = find_sumo_home()
    assert sumo_home is not None, "SUMO_HOME was not found."
    assert sumo_home.exists(), f"SUMO_HOME does not exist: {sumo_home}"

    sumo_bin = get_sumo_binary(gui=False)
    assert Path(sumo_bin).exists(), f"sumo binary not found at: {sumo_bin}"

    netconvert_bin = get_netconvert_binary()
    assert Path(netconvert_bin).exists(), f"netconvert binary not found at: {netconvert_bin}"


def test_network_generation(tmp_path):
    """Test generating 4-way intersection XML network files."""
    net_file = generate_network(output_dir=tmp_path, arm_length=200.0)
    assert net_file.exists(), "Compiled .net.xml file was not created."
    assert net_file.stat().st_size > 500, "Network file is unexpectedly small."

    tree = ET.parse(net_file)
    root = tree.getroot()

    # Verify junction J0 exists
    junction_ids = [j.get("id") for j in root.findall("junction")]
    assert "J0" in junction_ids, "Junction 'J0' missing from network."

    # Verify traffic light logic exists
    tl_logics = root.findall("tlLogic")
    assert len(tl_logics) > 0, "No traffic light logic in generated network."
    assert tl_logics[0].get("id") == "J0"


def test_demand_generation(tmp_path):
    """Test generating route files for multiple scenarios."""
    for sc in ("low", "normal", "rush_hour"):
        out_file = tmp_path / f"{sc}.rou.xml"
        generate_demand(scenario=sc, duration=100, seed=42, output_path=out_file)
        assert out_file.exists()

        tree = ET.parse(out_file)
        root = tree.getroot()
        vehicles = root.findall("vehicle")
        assert len(vehicles) > 0, f"No vehicles generated for scenario {sc}"


def test_headless_simulation_step():
    """Run a short 15s simulation to verify end-to-end execution and metrics."""
    summary, step_df = run_simulation(
        controller=None,
        scenario="normal",
        duration=15,
        seed=1,
        gui=False,
    )
    assert summary is not None
    assert "completed_vehicles" in summary
    assert "avg_queue_length" in summary
    assert len(step_df) == 15
