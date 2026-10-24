"""FastAPI Backend Server for Modern Custom Traffic Simulation Dashboard.

Provides REST and Server-Sent Events (SSE) streaming APIs for real-time
microscopic vehicle tracking, controller orchestration, benchmark comparisons,
and interactive interventions (emergency vehicle injection, traffic surges, signal overrides).
"""

from __future__ import annotations

import asyncio
import json
import queue
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from configs.default_config import DEFAULT_SIM_CONFIG
from controllers.adaptive import AdaptiveController
from controllers.fixed_time import FixedTimeController
from controllers.rl_controller import RLTrafficController
from evaluation.metrics import MetricsCollector
from simulation.generate_demand import SCENARIOS, generate_demand
from simulation.generate_network import generate_network
from simulation.sumo_utils import close_traci_safely, get_sumo_binary, setup_sumo_environment

setup_sumo_environment()
import traci

app = FastAPI(title="TrafficMind Intelligent Intersection API", version="2.5.0")

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
        self.event_queue: queue.Queue = queue.Queue(maxsize=150)
        self.lock = threading.Lock()
        self.latest_summary: Optional[Dict[str, Any]] = None
        self.worker_thread: Optional[threading.Thread] = None

        # Interactive live interventions
        self.pending_injections: List[Dict[str, Any]] = []
        self.manual_override_phase: Optional[int] = None
        self.manual_override_ticks: int = 0
        self.speed_factor: float = 1.0

    def stop(self):
        with self.lock:
            self.stop_requested = True

    def inject_vehicle(self, veh_type: str, origin: str, route_id: Optional[str] = None):
        with self.lock:
            self.pending_injections.append({
                "type": veh_type,  # 'emergency' or 'passenger'
                "origin": origin,  # 'N', 'S', 'E', 'W'
                "route_id": route_id,
            })

    def set_override(self, phase: int, duration_ticks: int = 15):
        with self.lock:
            self.manual_override_phase = phase
            self.manual_override_ticks = duration_ticks

    def set_speed(self, speed: float):
        with self.lock:
            self.speed_factor = max(0.0, min(5.0, speed))


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


class EmergencyInjectRequest(BaseModel):
    origin: str = "N"  # 'N', 'S', 'E', 'W'
    veh_type: str = "emergency"  # 'emergency' or 'passenger'


class ManualOverrideRequest(BaseModel):
    phase: int  # 0: NS Green, 2: EW Green
    duration: int = 15  # seconds to lock phase


class SpeedChangeRequest(BaseModel):
    speed: float = 1.0


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
        "manual_override_active": sim_manager.manual_override_phase is not None,
        "manual_override_phase": sim_manager.manual_override_phase,
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


@app.post("/api/intervention/inject-emergency")
def inject_emergency_vehicle(req: EmergencyInjectRequest):
    if not sim_manager.is_running:
        raise HTTPException(status_code=400, detail="Simulation must be running to inject vehicles.")
    sim_manager.inject_vehicle(veh_type=req.veh_type, origin=req.origin.upper())
    return {"message": f"Queued {req.veh_type} vehicle injection from origin {req.origin.upper()}"}


@app.post("/api/intervention/override-signal")
def override_signal_phase(req: ManualOverrideRequest):
    if not sim_manager.is_running:
        raise HTTPException(status_code=400, detail="Simulation must be running to override signal.")
    sim_manager.set_override(phase=req.phase, duration_ticks=req.duration)
    return {"message": f"Overriding signal to phase {req.phase} for {req.duration}s"}


@app.post("/api/intervention/speed")
def update_playback_speed(req: SpeedChangeRequest):
    sim_manager.set_speed(req.speed)
    return {"message": f"Playback speed updated to {req.speed}x"}


def _simulation_worker(req: StartSimRequest):
    sim_manager.is_running = True
    sim_manager.stop_requested = False
    sim_manager.current_step = 0
    sim_manager.total_duration = req.duration
    sim_manager.controller_name = req.controller
    sim_manager.scenario_name = req.scenario
    sim_manager.speed_factor = req.speed_factor
    sim_manager.manual_override_phase = None
    sim_manager.manual_override_ticks = 0
    with sim_manager.lock:
        sim_manager.pending_injections.clear()

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
            controller = AdaptiveController()

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

    emergency_counter = 0

    try:
        traci.start(sumo_cmd)
        tls_id = config.tls_id

        # Register custom vehicle types if available
        try:
            traci.vehicletype.copy("passenger", "emergency_vtype")
            traci.vehicletype.setColor("emergency_vtype", (255, 30, 80, 255))
            traci.vehicletype.setMaxSpeed("emergency_vtype", 22.0)
            traci.vehicletype.setAccel("emergency_vtype", 4.0)
        except Exception:
            pass

        current_phase = traci.trafficlight.getPhase(tls_id)
        phase_duration = 0

        # Predefined routes per arm for dynamic vehicle spawning
        arm_routes = {
            "N": "r_N_S",
            "S": "r_S_N",
            "E": "r_E_W",
            "W": "r_W_E",
        }

        for step in range(req.duration):
            if sim_manager.stop_requested:
                break

            sim_manager.current_step = step

            # Process any queued vehicle injections (e.g., Emergency Ambulance or Traffic Burst)
            with sim_manager.lock:
                injections = list(sim_manager.pending_injections)
                sim_manager.pending_injections.clear()

            for inj in injections:
                emergency_counter += 1
                origin = inj.get("origin", "N")
                veh_type = inj.get("type", "emergency")
                route_id = inj.get("route_id") or arm_routes.get(origin, "r_N_S")
                vid = f"{'EMERGENCY' if veh_type == 'emergency' else 'SURGE'}_{origin}_{step}_{emergency_counter}"
                vtype_name = "emergency_vtype" if veh_type == "emergency" else "passenger"
                try:
                    traci.vehicle.add(
                        vehID=vid,
                        routeID=route_id,
                        typeID=vtype_name,
                        depart=f"{step}",
                        departLane="best",
                        departSpeed="max",
                    )
                    if veh_type == "emergency":
                        traci.vehicle.setColor(vid, (255, 30, 80, 255))
                except Exception as e:
                    print(f"Vehicle injection error: {e}")

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

            # Phase Decision (Manual Override vs AI Controller)
            desired_phase = current_phase
            with sim_manager.lock:
                if sim_manager.manual_override_ticks > 0 and sim_manager.manual_override_phase is not None:
                    desired_phase = sim_manager.manual_override_phase
                    sim_manager.manual_override_ticks -= 1
                    if sim_manager.manual_override_ticks <= 0:
                        sim_manager.manual_override_phase = None
                else:
                    if controller:
                        desired_phase = controller.step(current_time=step, state=state)
                    else:
                        desired_phase = traci.trafficlight.getPhase(tls_id)

            if desired_phase != current_phase:
                traci.trafficlight.setPhase(tls_id, desired_phase)
                current_phase = desired_phase
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

            # Microscopic vehicle positions for live radar canvas / 3D viewport
            vehicles_frame: List[Dict[str, Any]] = []
            for vid in active_vids[:120]:
                try:
                    pos = traci.vehicle.getPosition(vid)
                    angle = traci.vehicle.getAngle(vid)
                    speed = traci.vehicle.getSpeed(vid)
                    waiting = traci.vehicle.getAccumulatedWaitingTime(vid)
                    edge = traci.vehicle.getRoadID(vid)
                    origin = edge.split("_")[0] if "_" in edge else "N"
                    is_emergency = "EMERGENCY" in vid or vid.startswith("e_")
                    vehicles_frame.append({
                        "id": vid,
                        "x": round(pos[0], 2),
                        "y": round(pos[1], 2),
                        "angle": round(angle, 1),
                        "speed": round(speed, 2),
                        "wait": round(waiting, 1),
                        "origin": origin,
                        "isEmergency": is_emergency,
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
                "manual_override_active": sim_manager.manual_override_phase is not None,
                "manual_override_phase": sim_manager.manual_override_phase,
                "manual_override_remaining": sim_manager.manual_override_ticks,
            }

            # Put in queue non-blocking (drop oldest if full)
            if sim_manager.event_queue.full():
                try:
                    sim_manager.event_queue.get_nowait()
                except Exception:
                    pass
            sim_manager.event_queue.put(frame)

            # Throttle playback
            sp = sim_manager.speed_factor
            if sp > 0:
                time.sleep(0.04 * sp)

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
                await asyncio.sleep(0.03)
            await asyncio.sleep(0.015)

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


# Mount modern web static assets
web_dist_dir = PROJECT_ROOT / "web" / "dist"
legacy_static_dir = Path(__file__).resolve().parent / "static"

if web_dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dist_dir), html=True), name="static")
else:
    legacy_static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(legacy_static_dir), html=True), name="static")



if __name__ == "__main__":
    import uvicorn
    print("Launching TrafficMind Intelligent Intersection API at http://localhost:8000")
    uvicorn.run("dashboard.server:app", host="0.0.0.0", port=8000, reload=False)
