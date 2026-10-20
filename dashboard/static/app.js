/**
 * Traffic Chaos Simulator — Client-Side Platform Engine
 * Real-time microscopic canvas radar, SSE telemetry streaming, and dynamic charts.
 */

// Global State
const state = {
  selectedController: "adaptive",
  selectedScenario: "normal",
  duration: 120,
  seed: 42,
  speed: 1.0,
  isRunning: false,
  eventSource: null,
  chart: null,
  chartHistoryLength: 30,
};

// Canvas & Context
const canvas = document.getElementById("traffic-canvas");
const ctx = canvas.getContext("2d");
const CANVAS_WIDTH = 600;
const CANVAS_HEIGHT = 520;
const CENTER_X = CANVAS_WIDTH / 2;
const CENTER_Y = CANVAS_HEIGHT / 2;
const SCALE = 0.95; // pixels per simulation meter

// DOM Elements
const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");
const btnBenchmark = document.getElementById("btn-benchmark");
const overlay = document.getElementById("canvas-overlay");
const statusChip = document.getElementById("system-status");
const statusLabel = document.getElementById("status-label");
const hudTimer = document.getElementById("hud-timer");

// KPIs
const valWait = document.getElementById("kpi-val-wait");
const valQueue = document.getElementById("kpi-val-queue");
const valTp = document.getElementById("kpi-val-tp");
const valActive = document.getElementById("kpi-val-active");
const badgeWait = document.getElementById("kpi-badge-wait");
const badgeQueue = document.getElementById("kpi-badge-queue");
const badgeMaxWait = document.getElementById("kpi-badge-maxwait");

// Signal Indicators
const lightNS = document.getElementById("hud-light-ns");
const lightEW = document.getElementById("hud-light-ew");

// Approach Progress
const progN = document.getElementById("prog-n");
const progS = document.getElementById("prog-s");
const progE = document.getElementById("prog-e");
const progW = document.getElementById("prog-w");
const valN = document.getElementById("app-val-n");
const valS = document.getElementById("app-val-s");
const valE = document.getElementById("app-val-e");
const valW = document.getElementById("app-val-w");
const subN = document.getElementById("sub-n");
const subS = document.getElementById("sub-s");
const subE = document.getElementById("sub-e");
const subW = document.getElementById("sub-w");

// Benchmark Modal
const modalBenchmark = document.getElementById("benchmark-modal");
const btnCloseModal = document.getElementById("btn-close-modal");
const benchLoading = document.getElementById("benchmark-loading");
const benchContent = document.getElementById("benchmark-content");
const benchTbody = document.getElementById("benchmark-tbody");


// =============================================================================
// Initialization
// =============================================================================

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  initChart();
  drawIntersectionBase();
  fetchInitialStatus();
});

function setupEventListeners() {
  // Controller selection
  document.querySelectorAll(".ctrl-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ctrl-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.selectedController = btn.dataset.controller;
    });
  });

  // Scenario selection
  document.querySelectorAll(".pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      state.selectedScenario = pill.dataset.scenario;
    });
  });

  // Sliders
  const inDur = document.getElementById("input-duration");
  const inSeed = document.getElementById("input-seed");
  const inSpd = document.getElementById("input-speed");

  inDur.addEventListener("input", (e) => {
    state.duration = parseInt(e.target.value);
    document.getElementById("val-duration").innerText = `${state.duration}s`;
    updateTimerHUD(0, state.duration);
  });

  inSeed.addEventListener("input", (e) => {
    state.seed = parseInt(e.target.value);
    document.getElementById("val-seed").innerText = state.seed;
  });

  inSpd.addEventListener("input", (e) => {
    state.speed = parseFloat(e.target.value);
    document.getElementById("val-speed").innerText = `${state.speed}x`;
  });

  // Buttons
  btnStart.addEventListener("click", startSimulation);
  btnStop.addEventListener("click", stopSimulation);
  btnBenchmark.addEventListener("click", openBenchmarkModal);
  btnCloseModal.addEventListener("click", () => modalBenchmark.classList.remove("active"));
}

async function fetchInitialStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.status === "running") {
      connectSSE();
    }
  } catch (err) {
    console.warn("Could not reach API status:", err);
  }
}


// =============================================================================
// Simulation Lifecycle & SSE Telemetry
// =============================================================================

async function startSimulation() {
  btnStart.disabled = true;
  btnStop.disabled = false;
  overlay.classList.add("hidden");

  statusChip.className = "status-chip running";
  statusLabel.innerText = "SIMULATING LIVE";

  // Reset Chart
  resetChart();

  try {
    const res = await fetch("/api/simulation/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        controller: state.selectedController,
        scenario: state.selectedScenario,
        duration: state.duration,
        seed: state.seed,
        speed_factor: 1.0 / state.speed,
        launch_gui: false,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Error starting simulation: ${err.detail || "Failed"}`);
      resetUI();
      return;
    }

    state.isRunning = true;
    connectSSE();
  } catch (err) {
    console.error("Simulation request error:", err);
    resetUI();
  }
}

async function stopSimulation() {
  try {
    await fetch("/api/simulation/stop", { method: "POST" });
  } catch (e) {}
  if (state.eventSource) {
    state.eventSource.close();
  }
  resetUI();
}

function connectSSE() {
  if (state.eventSource) {
    state.eventSource.close();
  }

  state.eventSource = new EventSource("/api/simulation/stream");

  state.eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "telemetry") {
        handleTelemetryFrame(data);
      } else if (data.type === "completed" || data.type === "idle") {
        if (state.eventSource) state.eventSource.close();
        resetUI();
        if (data.summary) {
          alert(`Simulation Finished!\nCompleted Vehicles: ${data.summary.completed_vehicles}\nAvg Waiting Time: ${data.summary.avg_waiting_time_sec}s`);
        }
      }
    } catch (err) {
      console.error("SSE parse error:", err);
    }
  };

  state.eventSource.onerror = () => {
    if (state.eventSource) state.eventSource.close();
    resetUI();
  };
}

function resetUI() {
  state.isRunning = false;
  btnStart.disabled = false;
  btnStop.disabled = true;
  statusChip.className = "status-chip";
  statusLabel.innerText = "SIMULATOR READY";
  overlay.classList.remove("hidden");
}

function handleTelemetryFrame(frame) {
  // 1. Update Timer
  updateTimerHUD(frame.step, frame.total_duration);

  // 2. Update Signal Lights
  updateTrafficLights(frame.current_phase, frame.tls_state);

  // 3. Update KPIs
  valQueue.innerText = frame.total_queue;
  valActive.innerText = frame.total_active;
  badgeMaxWait.innerText = `Max Wait: ${frame.max_wait}s`;

  // Calculate live average wait from active approach waits
  const sumWait = Object.values(frame.waiting_times).reduce((a, b) => a + b, 0);
  const avgWait = frame.total_active > 0 ? (sumWait / frame.total_active).toFixed(2) : "0.00";
  valWait.innerText = avgWait;

  // Approximate throughput
  const elapsedMinutes = (frame.step + 1) / 60.0;
  const tp = elapsedMinutes > 0 ? (frame.total_active * 0.4 / elapsedMinutes).toFixed(1) : "0.0";
  valTp.innerText = tp;

  // KPI badges
  if (frame.total_queue > 8) {
    badgeQueue.className = "kpi-badge alert";
    badgeQueue.innerText = "Congestion Alert";
  } else {
    badgeQueue.className = "kpi-badge good";
    badgeQueue.innerText = "Clear Corridors";
  }

  // 4. Update Approach Progress Bars
  updateApproachCard("N", frame.queues.N || 0, frame.waiting_times.N || 0.0);
  updateApproachCard("S", frame.queues.S || 0, frame.waiting_times.S || 0.0);
  updateApproachCard("E", frame.queues.E || 0, frame.waiting_times.E || 0.0);
  updateApproachCard("W", frame.queues.W || 0, frame.waiting_times.W || 0.0);

  // 5. Update Chart
  pushChartData(frame.step, frame.total_queue, parseFloat(avgWait));

  // 6. Draw Real-time Canvas Radar
  renderCanvasRadar(frame.vehicles || [], frame.current_phase);
}

function updateTimerHUD(step, total) {
  const pad = (n) => String(Math.floor(n)).padStart(2, "0");
  const m1 = pad(step / 60);
  const s1 = pad(step % 60);
  const m2 = pad(total / 60);
  const s2 = pad(total % 60);
  hudTimer.innerText = `${m1}:${s1} / ${m2}:${s2}`;
}

function updateTrafficLights(phase, stateStr) {
  // Phase 0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow
  const isNSGreen = phase === 0;
  const isNSYellow = phase === 1;
  const isEWGreen = phase === 2;
  const isEWYellow = phase === 3;

  setLightPill(lightNS, isNSGreen ? "green" : isNSYellow ? "yellow" : "red");
  setLightPill(lightEW, isEWGreen ? "green" : isEWYellow ? "yellow" : "red");
}

function setLightPill(container, activeColor) {
  container.querySelectorAll(".light").forEach((l) => l.classList.remove("active"));
  const target = container.querySelector(`.light.${activeColor}`);
  if (target) target.classList.add("active");
}

function updateApproachCard(arm, queue, wait) {
  const cap = 15;
  const pct = Math.min((queue / cap) * 100, 100);
  const fill = document.getElementById(`prog-${arm.toLowerCase()}`);
  const val = document.getElementById(`app-val-${arm.toLowerCase()}`);
  const sub = document.getElementById(`sub-${arm.toLowerCase()}`);

  if (fill) fill.style.width = `${pct}%`;
  if (val) val.innerText = `${queue} veh`;
  if (sub) sub.innerText = `Wait: ${wait.toFixed(1)}s`;
}


// =============================================================================
// HTML5 2D Intersection Canvas Radar
// =============================================================================

function drawIntersectionBase() {
  ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

  // Background
  ctx.fillStyle = "#070b16";
  ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

  const roadWidth = 84;
  const halfRoad = roadWidth / 2;

  // Draw Roads (Asphalt)
  ctx.fillStyle = "#161f30";
  // Vertical Road (North - South)
  ctx.fillRect(CENTER_X - halfRoad, 0, roadWidth, CANVAS_HEIGHT);
  // Horizontal Road (East - West)
  ctx.fillRect(0, CENTER_Y - halfRoad, CANVAS_WIDTH, roadWidth);

  // Center Junction Square
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(CENTER_X - halfRoad, CENTER_Y - halfRoad, roadWidth, roadWidth);

  // Lane Dividers (Dashed Yellow/White)
  ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([8, 8]);

  // North divider
  ctx.beginPath();
  ctx.moveTo(CENTER_X, 0);
  ctx.lineTo(CENTER_X, CENTER_Y - halfRoad);
  ctx.stroke();

  // South divider
  ctx.beginPath();
  ctx.moveTo(CENTER_X, CENTER_Y + halfRoad);
  ctx.lineTo(CENTER_X, CANVAS_HEIGHT);
  ctx.stroke();

  // East divider
  ctx.beginPath();
  ctx.moveTo(CENTER_X + halfRoad, CENTER_Y);
  ctx.lineTo(CANVAS_WIDTH, CENTER_Y);
  ctx.stroke();

  // West divider
  ctx.beginPath();
  ctx.moveTo(0, CENTER_Y);
  ctx.lineTo(CENTER_X - halfRoad, CENTER_Y);
  ctx.stroke();

  ctx.setLineDash([]); // Reset dash

  // Stop Lines (Solid White)
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 3.5;

  // North incoming stop line
  ctx.beginPath();
  ctx.moveTo(CENTER_X - halfRoad, CENTER_Y - halfRoad);
  ctx.lineTo(CENTER_X, CENTER_Y - halfRoad);
  ctx.stroke();

  // South incoming stop line
  ctx.beginPath();
  ctx.moveTo(CENTER_X, CENTER_Y + halfRoad);
  ctx.lineTo(CENTER_X + halfRoad, CENTER_Y + halfRoad);
  ctx.stroke();

  // East incoming stop line
  ctx.beginPath();
  ctx.moveTo(CENTER_X + halfRoad, CENTER_Y - halfRoad);
  ctx.lineTo(CENTER_X + halfRoad, CENTER_Y);
  ctx.stroke();

  // West incoming stop line
  ctx.beginPath();
  ctx.moveTo(CENTER_X - halfRoad, CENTER_Y);
  ctx.lineTo(CENTER_X - halfRoad, CENTER_Y + halfRoad);
  ctx.stroke();

  // Approach Labels
  ctx.fillStyle = "rgba(148, 163, 184, 0.4)";
  ctx.font = "600 11px Plus Jakarta Sans";
  ctx.fillText("NORTH", CENTER_X - 18, 22);
  ctx.fillText("SOUTH", CENTER_X - 18, CANVAS_HEIGHT - 12);
  ctx.fillText("WEST", 14, CENTER_Y - 48);
  ctx.fillText("EAST", CANVAS_WIDTH - 46, CENTER_Y - 48);
}

function renderCanvasRadar(vehicles, phase) {
  drawIntersectionBase();

  const isNSGreen = phase === 0;
  const isNSYellow = phase === 1;
  const isEWGreen = phase === 2;
  const isEWYellow = phase === 3;

  // Draw Signal Glowing Stop Bars
  const roadWidth = 84;
  const halfRoad = roadWidth / 2;

  drawSignalGlow(
    CENTER_X - halfRoad, CENTER_Y - halfRoad, CENTER_X, CENTER_Y - halfRoad,
    isNSGreen ? "#10b981" : isNSYellow ? "#f59e0b" : "#ef4444"
  );
  drawSignalGlow(
    CENTER_X, CENTER_Y + halfRoad, CENTER_X + halfRoad, CENTER_Y + halfRoad,
    isNSGreen ? "#10b981" : isNSYellow ? "#f59e0b" : "#ef4444"
  );
  drawSignalGlow(
    CENTER_X + halfRoad, CENTER_Y - halfRoad, CENTER_X + halfRoad, CENTER_Y,
    isEWGreen ? "#10b981" : isEWYellow ? "#f59e0b" : "#ef4444"
  );
  drawSignalGlow(
    CENTER_X - halfRoad, CENTER_Y, CENTER_X - halfRoad, CENTER_Y + halfRoad,
    isEWGreen ? "#10b981" : isEWYellow ? "#f59e0b" : "#ef4444"
  );

  // Render Vehicles directly from SUMO coordinates
  for (const v of vehicles) {
    // In SUMO intersection, J0 is at (0, 0), arm length = 250m
    // Map SUMO x in [-250, 250] -> canvas X
    const canvasX = CENTER_X + v.x * SCALE;
    // Map SUMO y in [-250, 250] -> canvas Y (invert Y since screen Y is down)
    const canvasY = CENTER_Y - v.y * SCALE;

    if (canvasX < 5 || canvasX > CANVAS_WIDTH - 5 || canvasY < 5 || canvasY > CANVAS_HEIGHT - 5) {
      continue;
    }

    ctx.save();
    ctx.translate(canvasX, canvasY);
    // SUMO angle: 0 is North (up), 90 is East (right), clockwise
    ctx.rotate((v.angle * Math.PI) / 180);

    // Car body styling
    const isStopped = v.speed < 0.1;
    const bodyColor = isStopped ? "#f43f5e" : "#00f0ff";

    // Glow if queued
    if (isStopped && v.wait > 5) {
      ctx.shadowColor = "#f43f5e";
      ctx.shadowBlur = 8;
    }

    // Car Body
    ctx.fillStyle = bodyColor;
    ctx.beginPath();
    ctx.roundRect(-4, -8, 8, 16, 2.5);
    ctx.fill();

    // Windshield
    ctx.fillStyle = "#0b1329";
    ctx.fillRect(-3, -4, 6, 4);

    // Headlights (facing forward: up in car rotation)
    ctx.fillStyle = "#fef08a";
    ctx.fillRect(-3, -9, 2, 1.5);
    ctx.fillRect(1, -9, 2, 1.5);

    // Tail / Brake lights
    ctx.fillStyle = isStopped ? "#ef4444" : "#991b1b";
    ctx.fillRect(-3, 7.5, 2, 1.5);
    ctx.fillRect(1, 7.5, 2, 1.5);

    ctx.restore();
  }
}

function drawSignalGlow(x1, y1, x2, y2, color) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 4;
  ctx.shadowColor = color;
  ctx.shadowBlur = 12;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  ctx.restore();
}


// =============================================================================
// Live Dynamic Chart.js
// =============================================================================

function initChart() {
  const chartCanvas = document.getElementById("live-chart");
  state.chart = new Chart(chartCanvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Total Queue (veh)",
          borderColor: "#00f0ff",
          backgroundColor: "rgba(0, 240, 255, 0.08)",
          borderWidth: 2.2,
          pointRadius: 0,
          fill: true,
          tension: 0.35,
          data: [],
          yAxisID: "y",
        },
        {
          label: "Avg Wait (s)",
          borderColor: "#f59e0b",
          backgroundColor: "transparent",
          borderWidth: 1.8,
          borderDash: [5, 5],
          pointRadius: 0,
          tension: 0.35,
          data: [],
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans", size: 10 } },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(148, 163, 184, 0.06)" },
          ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 9 } },
        },
        y: {
          position: "left",
          min: 0,
          suggestedMax: 10,
          grid: { color: "rgba(148, 163, 184, 0.06)" },
          ticks: { color: "#00f0ff", font: { family: "JetBrains Mono", size: 9 } },
        },
        y1: {
          position: "right",
          min: 0,
          suggestedMax: 20,
          grid: { drawOnChartArea: false },
          ticks: { color: "#f59e0b", font: { family: "JetBrains Mono", size: 9 } },
        },
      },
    },
  });
}

function pushChartData(step, queue, wait) {
  if (!state.chart) return;
  const labels = state.chart.data.labels;
  const dQueue = state.chart.data.datasets[0].data;
  const dWait = state.chart.data.datasets[1].data;

  labels.push(`${step}s`);
  dQueue.push(queue);
  dWait.push(wait);

  if (labels.length > state.chartHistoryLength) {
    labels.shift();
    dQueue.shift();
    dWait.shift();
  }

  state.chart.update();
}

function resetChart() {
  if (!state.chart) return;
  state.chart.data.labels = [];
  state.chart.data.datasets[0].data = [];
  state.chart.data.datasets[1].data = [];
  state.chart.update();
}


// =============================================================================
// Head-to-Head 3-Way Benchmark Modal
// =============================================================================

async function openBenchmarkModal() {
  modalBenchmark.classList.add("active");
  benchLoading.classList.remove("hidden");
  benchContent.classList.add("hidden");

  try {
    const res = await fetch("/api/benchmark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenarios: ["normal", "unbalanced", "rush_hour"],
        duration: 100,
        seed: state.seed,
      }),
    });

    const data = await res.json();
    benchTbody.innerHTML = "";

    for (const r of data.results) {
      const tr = document.createElement("tr");
      const ctrlName = r.controller.replace("Controller", "");
      const isRL = ctrlName.includes("RL");
      const isAdaptive = ctrlName.includes("Adaptive");

      const badgeStyle = isRL
        ? "color: #34d399; font-weight: bold;"
        : isAdaptive
        ? "color: #38bdf8; font-weight: bold;"
        : "color: #94a3b8;";

      tr.innerHTML = `
        <td><span class="pill" style="padding: 3px 8px; font-size: 0.72rem;">${r.scenario}</span></td>
        <td style="${badgeStyle}">${ctrlName}</td>
        <td><strong>${r.avg_waiting_time_sec.toFixed(2)}s</strong></td>
        <td>${r.avg_queue_length.toFixed(2)} veh</td>
        <td>${r.throughput_per_minute.toFixed(1)} /min</td>
        <td>${r.max_waiting_time_sec.toFixed(1)}s</td>
        <td>${r.completed_vehicles}</td>
      `;
      benchTbody.appendChild(tr);
    }

    benchLoading.classList.add("hidden");
    benchContent.classList.remove("hidden");
  } catch (err) {
    benchLoading.innerHTML = `<p style="color: #f43f5e;">Benchmark failed: ${err.message}</p>`;
  }
}
