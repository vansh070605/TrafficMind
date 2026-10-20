"""FastAPI Backend Server for Modern Custom Traffic Simulation Dashboard.

Provides REST and Server-Sent Events (SSE) streaming APIs for real-time
microscopic vehicle tracking, controller orchestration, and benchmark comparisons.
"""

from __future__ import annotations

import asyncio
import json
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from configs.default_config import DEFAULT_SIM_CONFIG, SimulationConfig
from controllers.adaptive import AdaptiveController
from controllers.fixed_time import FixedTimeController
from controllers.rl_controller import RLTrafficController
from evaluation.metrics import MetricsCollector
from simulation.generate_demand import SCENARIOS, generate_demand
from simulation.generate_network import generate_network
from simulation.sumo_utils import close_traci_safely, get_sumo_binary, setup_sumo_environment

setup_sumo_environment()
import traci

app = FastAPI(title="Traffic Chaos Simulator API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Simulation Worker State
class SimulationManager:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False
        self.current_step = 0
        self.total_duration = 0
        self.controller_name = "Fixed-Time"
        self.scenario_name = "normal"
        self.event_queue: queue.Queue = queue.Queue(maxsize=100)
        self.lock = threading.Lock()
        self.latest_summary: Optional[Dict[str, Any]] = None
        self.worker_thread: Optional[threading.Thread] = None

    def stop(self):
        with self.lock:
            self.stop_requested = True


sim_manager = SimulationManager()


class StartSimRequest(BaseModel):
    controller: str = "adaptive"  # 'fixed', 'adaptive', 'rl'
    scenario: str = "normal"
    duration: int = 150
    seed: int = 42
    speed_factor: float = 1.0  # delay multiplier
    launch_gui: bool = False


class BenchmarkRequest(BaseModel):
    scenarios: List[str] = ["normal", "unbalanced"]
    duration: int = 100
    seed: int = 42


@app.get("/api/status")
def get_status():
    model_path = PROJECT_ROOT / "outputs" / "models" / "ppo_traffic_final.zip"
    return {
        "status": "running" if sim_manager.is_running else "idle",
        "current_step": sim_manager.current_step,
        "total_duration": sim_manager.total_duration,
        "active_controller": sim_manager.controller_name,
        "active_scenario": sim_manager.scenario_name,
        "rl_model_available": model_path.exists(),
        "available_scenarios": list(SCENARIOS.keys()),
        "latest_summary": sim_manager.latest_summary,
    }


@app.get("/api/scenarios")
def get_scenarios():
    return {
        name: {
            "name": cfg.name,
            "description": cfg.description,
            "rates_ns": cfg.rates_ns,
            "rates_ew": cfg.rates_ew,
            "surge": cfg.surge_multiplier if cfg.surge_multiplier > 1.0 else None,
        }
        for name, cfg in SCENARIOS.items()
    }


def _simulation_worker(req: StartSimRequest):
    sim_manager.is_running = True
    sim_manager.stop_requested = False
    sim_manager.current_step = 0
    sim_manager.total_duration = req.duration
    sim_manager.controller_name = req.controller
    sim_manager.scenario_name = req.scenario

    config = DEFAULT_SIM_CONFIG
    close_traci_safely()

    # Network & demand
    net_file = config.net_file
    if not net_file.exists():
        net_file = generate_network(output_dir=config.network_dir, arm_length=config.arm_length)

    route_file = generate_demand(
        scenario=req.scenario,
        duration=req.duration,
        seed=req.seed,
        output_path=config.scenarios_dir / f"dash_{req.scenario}_s{req.seed}.rou.xml",
    )

    # Controller instantiation
    controller = None
    if req.controller == "fixed":
        controller = FixedTimeController()
    elif req.controller == "adaptive":
        controller = AdaptiveController()
    elif req.controller == "rl":
        model_p = PROJECT_ROOT / "outputs" / "models" / "ppo_traffic_final.zip"
        if model_p.exists():
            controller = RLTrafficController(model_path=model_p)
        else:
            controller = AdaptiveController()  # fallback

    sumo_bin = get_sumo_binary(gui=req.launch_gui)
    sumo_cmd = [
        sumo_bin,
        "-n", str(net_file),
        "-r", str(route_file),
        "--step-length", "1.0",
        "--time-to-teleport", "-1",
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--seed", str(req.seed),
    ]

    if req.launch_gui:
        sumo_cmd.extend(["--start", "true", "--quit-on-end", "true"])

    collector = MetricsCollector(sim_duration=req.duration)
    collector.start()
    if controller:
        controller.reset()

    try:
        traci.start(sumo_cmd)
        tls_id = config.tls_id

        current_phase = traci.trafficlight.getPhase(tls_id)
        phase_duration = 0

        for step in range(req.duration):
            if sim_manager.stop_requested:
                break

            sim_manager.current_step = step

            # Traffic State Extraction
            queues_by_arm: Dict[str, int] = {"N": 0, "S": 0, "E": 0, "W": 0}
            waits_by_arm: Dict[str, float] = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
            counts_by_arm: Dict[str, int] = {"N": 0, "S": 0, "E": 0, "W": 0}
            edge_data: Dict[str, Dict[str, Any]] = {}
            max_wait = 0.0

            for edge_id in config.incoming_edges:
                arm = edge_id.split("_")[0]
                q = traci.edge.getLastStepHaltingNumber(edge_id)
                w = traci.edge.getWaitingTime(edge_id)
                c = traci.edge.getLastStepVehicleNumber(edge_id)
                queues_by_arm[arm] += q
                waits_by_arm[arm] += w
                counts_by_arm[arm] += c
                edge_data[edge_id] = {"queue": q, "wait": w, "count": c}

            active_vids = traci.vehicle.getIDList()
            for vid in active_vids:
                try:
                    w = traci.vehicle.getAccumulatedWaitingTime(vid)
                    if w > max_wait:
                        max_wait = w
                except Exception:
                    pass

            state = {
                "current_phase": current_phase,
                "phase_duration": phase_duration,
                "queues": queues_by_arm,
                "waiting_times": waits_by_arm,
                "vehicle_counts": counts_by_arm,
                "max_waiting_time": max_wait,
                "edge_data": edge_data,
                "active_vehicle_ids": list(active_vids),
            }

            # Controller step
            if controller:
                desired_phase = controller.step(current_time=step, state=state)
                if desired_phase != current_phase:
                    traci.trafficlight.setPhase(tls_id, desired_phase)
                    current_phase = desired_phase
                    phase_duration = 0
                else:
                    phase_duration += 1
            else:
                new_phase = traci.trafficlight.getPhase(tls_id)
                if new_phase != current_phase:
                    current_phase = new_phase
                    phase_duration = 0
                else:
                    phase_duration += 1

            # Advance simulation 1 step
            traci.simulationStep()

            departed = traci.simulation.getDepartedIDList()
            arrived = traci.simulation.getArrivedIDList()

            collector.record_step(
                current_time=step,
                current_phase=current_phase,
                queues_by_arm=queues_by_arm,
                waits_by_arm=waits_by_arm,
                counts_by_arm=counts_by_arm,
                active_veh_ids=list(active_vids),
                departed_veh_ids=list(departed),
                arrived_veh_ids=list(arrived),
                traci_client=traci,
            )

            # Microscopic vehicle positions for live radar canvas
            vehicles_frame: List[Dict[str, Any]] = []
            for vid in active_vids[:80]:  # Cap for network performance
                try:
                    pos = traci.vehicle.getPosition(vid)
                    angle = traci.vehicle.getAngle(vid)
                    speed = traci.vehicle.getSpeed(vid)
                    waiting = traci.vehicle.getAccumulatedWaitingTime(vid)
                    edge = traci.vehicle.getRoadID(vid)
                    origin = edge.split("_")[0] if "_" in edge else "N"
                    vehicles_frame.append({
                        "id": vid,
                        "x": round(pos[0], 1),
                        "y": round(pos[1], 1),
                        "angle": round(angle, 1),
                        "speed": round(speed, 1),
                        "wait": round(waiting, 1),
                        "origin": origin,
                    })
                except Exception:
                    pass

            tls_state_str = traci.trafficlight.getRedYellowGreenState(tls_id)

            # Build real-time telemetry frame
            frame = {
                "type": "telemetry",
                "step": step,
                "total_duration": req.duration,
                "current_phase": current_phase,
                "tls_state": tls_state_str,
                "queues": queues_by_arm,
                "waiting_times": {k: round(v, 1) for k, v in waits_by_arm.items()},
                "counts": counts_by_arm,
                "total_queue": sum(queues_by_arm.values()),
                "total_active": len(active_vids),
                "max_wait": round(max_wait, 1),
                "vehicles": vehicles_frame,
            }

            # Put in queue non-blocking (drop oldest if full)
            if sim_manager.event_queue.full():
                try:
                    sim_manager.event_queue.get_nowait()
                except Exception:
                    pass
            sim_manager.event_queue.put(frame)

            # Throttle playback
            if req.speed_factor > 0:
                time.sleep(0.05 * req.speed_factor)

    finally:
        collector.finish()
        close_traci_safely()
        sim_manager.latest_summary = collector.get_summary()
        sim_manager.is_running = False

        # Put end frame
        try:
            sim_manager.event_queue.put({
                "type": "completed",
                "summary": sim_manager.latest_summary,
            })
        except Exception:
            pass


@app.post("/api/simulation/start")
def start_simulation(req: StartSimRequest):
    if sim_manager.is_running:
        raise HTTPException(status_code=400, detail="A simulation is already in progress.")

    # Clear event queue
    while not sim_manager.event_queue.empty():
        try:
            sim_manager.event_queue.get_nowait()
        except Exception:
            pass

    t = threading.Thread(target=_simulation_worker, args=(req,), daemon=True)
    sim_manager.worker_thread = t
    t.start()
    return {"message": "Simulation started", "config": req.dict()}


@app.post("/api/simulation/stop")
def stop_simulation():
    if not sim_manager.is_running:
        return {"message": "No active simulation"}
    sim_manager.stop()
    return {"message": "Stopping simulation..."}


@app.get("/api/simulation/stream")
async def stream_simulation():
    async def event_generator():
        while True:
            try:
                frame = sim_manager.event_queue.get_nowait()
                yield f"data: {json.dumps(frame)}\n\n"
                if frame.get("type") == "completed":
                    break
            except queue.Empty:
                if not sim_manager.is_running:
                    yield f"data: {json.dumps({'type': 'idle'})}\n\n"
                    break
                await asyncio.sleep(0.04)
            await asyncio.sleep(0.02)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/benchmark")
def run_benchmark_endpoint(req: BenchmarkRequest):
    """Run synchronous benchmark comparing all controllers on selected scenarios."""
    from evaluation.benchmarks import run_benchmarks
    df = run_benchmarks(
        scenarios=req.scenarios,
        seeds=[req.seed],
        duration=req.duration,
    )
    records = df.to_dict(orient="records")
    return {"results": records}


# Mount modern static assets
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("Launching Traffic Chaos Simulator Web Platform at http://localhost:8000")
    uvicorn.run("dashboard.server:app", host="0.0.0.0", port=8000, reload=False)
