# TrafficMind Web Dashboard

React 19 + TypeScript + Vite frontend for the TrafficMind simulator. It talks to the FastAPI backend in `dashboard/server.py` and renders live SUMO telemetry streamed over Server-Sent Events.

## Stack

- React 19, TypeScript, Vite 8
- Tailwind CSS v4 (`@tailwindcss/vite`)
- Three.js (3D intersection view), Vanta, GSAP, Lenis
- lucide-react icons, canvas-confetti
- Oxlint for linting

## Layout

```
src/
├── App.tsx                 # Top-level state, SSE subscription, API calls, tab navigation
├── main.tsx                # Entry point
├── types.ts                # Vehicle, TelemetryFrame, SimulationSummary types
├── vanta.d.ts              # Type shim for Vanta
└── components/
    ├── Viewport3D.tsx      # Three.js isometric intersection with animated vehicles and signals
    ├── Canvas2DRadar.tsx   # 2D canvas radar alternative view
    ├── ControlDeck.tsx     # Controller/scenario pickers, duration and speed sliders, interventions
    ├── TelemetryCards.tsx  # Live queue, delay, and max-wait stat cards
    ├── LiveChart.tsx       # Rolling queue/wait chart
    ├── ApproachFairness.tsx# Per-arm (N/S/E/W) load bars
    └── BenchmarkModal.tsx  # In-browser Fixed vs Adaptive vs RL comparison
```

## Development

Start the backend first from the repo root:

```bash
python dashboard/server.py
```

Then run the Vite dev server:

```bash
cd web
npm install
npm run dev
```

Vite serves on http://localhost:3000 and proxies `/api` to http://localhost:8000 (see `vite.config.ts`).

## Production build

```bash
npm run build
```

This writes `web/dist`, which `dashboard/server.py` mounts at `/` when it exists. `web/dist` is gitignored, so build it before launching the server.

## Scripts

| Script | Does |
| :--- | :--- |
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Type-check (`tsc -b`) and build to `dist/` |
| `npm run lint` | Run Oxlint |
| `npm run preview` | Serve the built `dist/` locally |

## Data flow

1. `POST /api/simulation/start` launches a run in a backend worker thread.
2. `App.tsx` opens an `EventSource` on `/api/simulation/stream`.
3. Each `telemetry` frame carries phase, signal state string, per-arm queues/waits/counts, and up to 120 vehicle positions.
4. A final `completed` frame carries the run summary.

See the root `README.md` for the full API table and known issues.
