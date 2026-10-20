"""Unit tests for metrics calculation, throughput, and summary statistics."""

from unittest.mock import MagicMock
import pytest

from evaluation.metrics import MetricsCollector


def test_metrics_collector_empty():
    """Verify metrics collector handles runs with zero vehicles gracefully."""
    collector = MetricsCollector(sim_duration=100)
    collector.start()
    collector.finish()
    summary = collector.get_summary()

    assert summary["total_vehicles_departed"] == 0
    assert summary["completed_vehicles"] == 0
    assert summary["completion_rate"] == 0.0
    assert summary["throughput_per_minute"] == 0.0
    assert summary["avg_waiting_time_sec"] == 0.0


def test_metrics_collector_trip_completion():
    """Verify trip duration, waiting times, and stops are tracked accurately."""
    collector = MetricsCollector(sim_duration=120)
    collector.start()

    mock_traci = MagicMock()
    mock_traci.vehicle.getRoute.return_value = ["N_to_J0", "J0_to_S"]
    mock_traci.vehicle.getSpeed.return_value = 0.0  # Stopped
    mock_traci.vehicle.getAccumulatedWaitingTime.return_value = 15.0

    # Step 10: Vehicle enters
    collector.record_step(
        current_time=10,
        current_phase=0,
        queues_by_arm={"N": 1, "S": 0, "E": 0, "W": 0},
        waits_by_arm={"N": 15.0, "S": 0.0, "E": 0.0, "W": 0.0},
        counts_by_arm={"N": 1, "S": 0, "E": 0, "W": 0},
        active_veh_ids=["veh_1"],
        departed_veh_ids=["veh_1"],
        arrived_veh_ids=[],
        traci_client=mock_traci,
    )

    # Step 50: Vehicle exits
    collector.record_step(
        current_time=50,
        current_phase=0,
        queues_by_arm={"N": 0, "S": 0, "E": 0, "W": 0},
        waits_by_arm={"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0},
        counts_by_arm={"N": 0, "S": 0, "E": 0, "W": 0},
        active_veh_ids=[],
        departed_veh_ids=[],
        arrived_veh_ids=["veh_1"],
        traci_client=mock_traci,
    )

    collector.finish()
    summary = collector.get_summary()

    assert summary["completed_vehicles"] == 1
    assert summary["uncompleted_vehicles"] == 0
    assert summary["completion_rate"] == 100.0
    # Trip duration = 50 - 10 = 40s
    assert summary["avg_trip_duration_sec"] == 40.0
    assert summary["avg_waiting_time_sec"] == 15.0
    # Throughput per minute: 1 veh / (120 / 60) = 0.50 veh/min
    assert summary["throughput_per_minute"] == 0.50
    # Directional record for North origin
    assert summary["directional"]["N"]["completed"] == 1
