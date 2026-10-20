"""Traffic Performance Metrics Collector and Evaluator.

Handles step-by-step and trip-level metrics collection:
- Average trip duration
- Average waiting time
- Average queue length
- Throughput per unit time
- Number of stops
- Maximum waiting time
- Directional breakdown (N, S, E, W)
- Proper handling of completed vs uncompleted trips
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass
class VehicleRecord:
    veh_id: str
    origin: str
    destination: str
    depart_time: float
    arrival_time: Optional[float] = None
    trip_duration: Optional[float] = None
    total_waiting_time: float = 0.0
    stops: int = 0
    is_completed: bool = False


class MetricsCollector:
    """Collects microscopic vehicle and intersection metrics during a simulation run."""

    def __init__(self, sim_duration: int = 1000) -> None:
        self.sim_duration = sim_duration
        self.wall_start_time: float = 0.0
        self.wall_end_time: float = 0.0

        # Step-level records
        self.step_history: List[Dict[str, Any]] = []

        # Vehicle-level tracking
        self.vehicles: Dict[str, VehicleRecord] = {}
        self.vehicle_prev_speed: Dict[str, float] = {}

    def start(self) -> None:
        """Mark simulation start time."""
        self.wall_start_time = time.perf_counter()

    def record_step(
        self,
        current_time: int,
        current_phase: int,
        queues_by_arm: Dict[str, int],
        waits_by_arm: Dict[str, float],
        counts_by_arm: Dict[str, int],
        active_veh_ids: List[str],
        departed_veh_ids: List[str],
        arrived_veh_ids: List[str],
        traci_client: Any,
    ) -> None:
        """Record metrics for the current simulation second."""
        total_queue = sum(queues_by_arm.values())
        total_wait = sum(waits_by_arm.values())
        total_active = len(active_veh_ids)

        # 1. Register newly departed vehicles
        for vid in departed_veh_ids:
            try:
                route = traci_client.vehicle.getRoute(vid)
                origin = route[0].split("_")[0] if route else "Unknown"
                destination = route[-1].split("_")[-1] if route else "Unknown"
            except Exception:
                origin, destination = "Unknown", "Unknown"

            self.vehicles[vid] = VehicleRecord(
                veh_id=vid,
                origin=origin,
                destination=destination,
                depart_time=float(current_time),
            )
            self.vehicle_prev_speed[vid] = 13.89

        # 2. Update stats for all currently active vehicles
        max_current_wait = 0.0
        for vid in active_veh_ids:
            try:
                speed = traci_client.vehicle.getSpeed(vid)
                wait = traci_client.vehicle.getAccumulatedWaitingTime(vid)
                if wait > max_current_wait:
                    max_current_wait = wait

                if vid in self.vehicles:
                    self.vehicles[vid].total_waiting_time = wait
                    prev_spd = self.vehicle_prev_speed.get(vid, 13.89)
                    if prev_spd > 0.1 and speed <= 0.1:
                        self.vehicles[vid].stops += 1
                    self.vehicle_prev_speed[vid] = speed
            except Exception:
                pass

        # 3. Finalize arrived vehicles
        for vid in arrived_veh_ids:
            if vid in self.vehicles:
                rec = self.vehicles[vid]
                rec.arrival_time = float(current_time)
                rec.trip_duration = rec.arrival_time - rec.depart_time
                rec.is_completed = True
                if vid in self.vehicle_prev_speed:
                    del self.vehicle_prev_speed[vid]

        # 4. Save step snapshot
        self.step_history.append({
            "step": current_time,
            "phase": current_phase,
            "total_queue": total_queue,
            "total_wait": total_wait,
            "active_vehicles": total_active,
            "max_current_wait": max_current_wait,
            "queue_N": queues_by_arm.get("N", 0),
            "queue_S": queues_by_arm.get("S", 0),
            "queue_E": queues_by_arm.get("E", 0),
            "queue_W": queues_by_arm.get("W", 0),
            "wait_N": waits_by_arm.get("N", 0.0),
            "wait_S": waits_by_arm.get("S", 0.0),
            "wait_E": waits_by_arm.get("E", 0.0),
            "wait_W": waits_by_arm.get("W", 0.0),
            "count_N": counts_by_arm.get("N", 0),
            "count_S": counts_by_arm.get("S", 0),
            "count_E": counts_by_arm.get("E", 0),
            "count_W": counts_by_arm.get("W", 0),
        })

    def finish(self) -> None:
        """Mark simulation completion time."""
        self.wall_end_time = time.perf_counter()

    def get_summary(self) -> Dict[str, Any]:
        """Compute aggregated performance metrics."""
        sim_wall_time = max(self.wall_end_time - self.wall_start_time, 0.001)

        completed_recs = [v for v in self.vehicles.values() if v.is_completed]
        uncompleted_recs = [v for v in self.vehicles.values() if not v.is_completed]
        all_recs = list(self.vehicles.values())

        num_completed = len(completed_recs)
        num_uncompleted = len(uncompleted_recs)
        total_vehicles = len(all_recs)

        # Durations & Waiting Times
        avg_trip_duration = float(np.mean([r.trip_duration for r in completed_recs])) if completed_recs else 0.0
        avg_wait_completed = float(np.mean([r.total_waiting_time for r in completed_recs])) if completed_recs else 0.0
        avg_wait_all = float(np.mean([r.total_waiting_time for r in all_recs])) if all_recs else 0.0
        max_waiting_time = float(max([r.total_waiting_time for r in all_recs])) if all_recs else 0.0

        avg_stops = float(np.mean([r.stops for r in completed_recs])) if completed_recs else 0.0

        # Queues from step history
        df_steps = pd.DataFrame(self.step_history) if self.step_history else pd.DataFrame()
        avg_queue = float(df_steps["total_queue"].mean()) if not df_steps.empty else 0.0
        max_queue = int(df_steps["total_queue"].max()) if not df_steps.empty else 0

        # Throughput
        throughput_per_minute = (num_completed / (self.sim_duration / 60.0)) if self.sim_duration > 0 else 0.0

        # Directional breakdown for completed trips
        directional: Dict[str, Dict[str, float]] = {}
        for arm in ("N", "S", "E", "W"):
            arm_recs = [r for r in completed_recs if r.origin == arm]
            directional[arm] = {
                "completed": len(arm_recs),
                "avg_duration": float(np.mean([r.trip_duration for r in arm_recs])) if arm_recs else 0.0,
                "avg_waiting_time": float(np.mean([r.total_waiting_time for r in arm_recs])) if arm_recs else 0.0,
                "avg_stops": float(np.mean([r.stops for r in arm_recs])) if arm_recs else 0.0,
            }

        return {
            "total_vehicles_departed": total_vehicles,
            "completed_vehicles": num_completed,
            "uncompleted_vehicles": num_uncompleted,
            "completion_rate": (num_completed / total_vehicles * 100.0) if total_vehicles > 0 else 0.0,
            "throughput_per_minute": round(throughput_per_minute, 2),
            "avg_trip_duration_sec": round(avg_trip_duration, 2),
            "avg_waiting_time_sec": round(avg_wait_completed, 2),
            "avg_waiting_time_all_sec": round(avg_wait_all, 2),
            "max_waiting_time_sec": round(max_waiting_time, 2),
            "avg_queue_length": round(avg_queue, 2),
            "max_queue_length": max_queue,
            "avg_stops_per_vehicle": round(avg_stops, 2),
            "wall_clock_time_sec": round(sim_wall_time, 3),
            "directional": directional,
        }

    def get_step_dataframe(self) -> pd.DataFrame:
        """Return the step-by-step history as a pandas DataFrame."""
        return pd.DataFrame(self.step_history)
