import React, { useState, useEffect, useRef, useCallback } from 'react';
import { gsap } from 'gsap';
import { Viewport3D } from './components/Viewport3D';
import { Canvas2DRadar } from './components/Canvas2DRadar';
import { ControlDeck } from './components/ControlDeck';
import { TelemetryCards } from './components/TelemetryCards';
import { LiveChart } from './components/LiveChart';
import { ApproachFairness } from './components/ApproachFairness';
import { BenchmarkModal } from './components/BenchmarkModal';
import type { TelemetryFrame, SimulationSummary } from './types';
import confetti from 'canvas-confetti';

type NavTab = 'overview' | 'radar' | 'control' | 'analytics' | 'fairness' | 'arena';

// ─── Infinite Marquee ────────────────────────────────────────
const Marquee: React.FC<{ text: string; bg?: string; color?: string; slow?: boolean; reverse?: boolean }> = ({
  text, bg = 'var(--black)', color = 'var(--yellow)', slow, reverse
}) => {
  const repeated = Array(12).fill(`${text}  ●  `).join('');
  return (
    <div style={{ background: bg, borderTop: '3px solid var(--black)', borderBottom: '3px solid var(--black)', overflow: 'hidden', padding: '10px 0' }}>
      <div className={`marquee-track ${slow ? 'marquee-track-slow' : ''} ${reverse ? 'marquee-track-rev' : ''}`}
           style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: '1.35rem', letterSpacing: '0.06em', color }}>
        {repeated}{repeated}
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('overview');
  const [viewMode, setViewMode]   = useState<'3d' | '2d'>('3d');
  const [isRunning, setIsRunning] = useState(false);
  const [selectedController, setSelectedController] = useState('adaptive');
  const [selectedScenario, setSelectedScenario]     = useState('normal');
  const [duration, setDuration]   = useState(120);
  const [speed, setSpeed]         = useState(1.0);
  const [isBenchmarkOpen, setIsBenchmarkOpen] = useState(false);

  // Live Telemetry State
  const [currentStep, setCurrentStep]         = useState(0);
  const [currentPhase, setCurrentPhase]       = useState(0);
  const [tlsState, setTlsState]               = useState('GGgrrrGGgrrr');
  const [vehicles, setVehicles]               = useState<any[]>([]);
  const [queues, setQueues]                   = useState<Record<string,number>>({ N:0, S:0, E:0, W:0 });
  const [waits, setWaits]                     = useState<Record<string,number>>({ N:0, S:0, E:0, W:0 });
  const [totalQueue, setTotalQueue]           = useState(0);
  const [activeVehicles, setActiveVehicles]   = useState(0);
  const [maxWait, setMaxWait]                 = useState(0);
  const [manualOverrideActive, setManualOverrideActive] = useState(false);
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryFrame[]>([]);
  const [latestSummary, setLatestSummary]     = useState<SimulationSummary | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const tabContentRef = useRef<HTMLDivElement>(null);

  // SSE Stream Listener
  const listenToStream = useCallback(() => {
    eventSourceRef.current?.close();
    const es = new EventSource('/api/simulation/stream');
    eventSourceRef.current = es;
    es.onmessage = (event) => {
      try {
        const frame: TelemetryFrame = JSON.parse(event.data);
        if (frame.type === 'telemetry') {
          setIsRunning(true);
          if (frame.step              !== undefined) setCurrentStep(frame.step);
          if (frame.current_phase     !== undefined) setCurrentPhase(frame.current_phase);
          if (frame.tls_state)                       setTlsState(frame.tls_state);
          if (frame.vehicles)                        setVehicles(frame.vehicles);
          if (frame.queues)                          setQueues(frame.queues);
          if (frame.waiting_times)                   setWaits(frame.waiting_times);
          if (frame.total_queue       !== undefined) setTotalQueue(frame.total_queue);
          if (frame.total_active      !== undefined) setActiveVehicles(frame.total_active);
          if (frame.max_wait          !== undefined) setMaxWait(frame.max_wait);
          setManualOverrideActive(!!frame.manual_override_active);
          setTelemetryHistory(prev => [...prev.slice(-60), frame]);
        } else if (frame.type === 'completed') {
          setIsRunning(false);
          if (frame.summary) {
            setLatestSummary(frame.summary);
            confetti({ particleCount: 160, spread: 80, origin: { y: 0.5 }, colors: ['#FFE500','#FF2D78','#7B2FFF','#AAFF00'] });
          }
          es.close();
        } else if (frame.type === 'idle') {
          setIsRunning(false);
          es.close();
        }
      } catch {}
    };
    es.onerror = () => { es.close(); setIsRunning(false); };
  }, []);

  // Initial status check
  useEffect(() => {
    fetch('/api/status').then(r => r.json()).then(d => {
      if (d.status === 'running') { setIsRunning(true); listenToStream(); }
    }).catch(() => {});
  }, [listenToStream]);

  // Tab change animation
  useEffect(() => {
    if (!tabContentRef.current) return;
    gsap.fromTo(tabContentRef.current,
      { opacity: 0, y: 16 },
      { opacity: 1, y: 0, duration: 0.25, ease: 'power2.out' }
    );
  }, [activeTab]);

  // Handlers
  const handleStartSim = async () => {
    setTelemetryHistory([]);
    setLatestSummary(null);
    try {
      const res = await fetch('/api/simulation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ controller: selectedController, scenario: selectedScenario, duration, seed: 42, speed_factor: speed }),
      });
      if (res.ok) { setIsRunning(true); listenToStream(); }
    } catch {}
  };

  const handleStopSim = async () => {
    try { await fetch('/api/simulation/stop', { method: 'POST' }); } catch {}
    setIsRunning(false);
    eventSourceRef.current?.close();
  };

  const handleInjectEmergency = async (origin: string) => {
    try {
      await fetch('/api/intervention/inject-emergency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ origin, veh_type: 'emergency' })
      });
    } catch {}
  };

  const handleOverrideSignal = async (phase: number) => {
    try {
      await fetch('/api/intervention/override-signal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phase, duration: 15 })
      });
    } catch {}
  };

  const handleSpeedChange = (s: number) => {
    setSpeed(s);
    fetch('/api/intervention/speed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ speed: s })
    }).catch(() => {});
  };

  const avgWait = Object.values(waits).reduce((a, b) => a + b, 0) / (Object.values(waits).length || 1);
  const throughput = latestSummary?.throughput_per_minute ?? (currentStep > 0 ? (latestSummary?.completed_vehicles ?? 0) / (currentStep / 60) : 0);
  const fmt = (s: number) => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;

  const tabs: { id: NavTab; label: string; icon: string }[] = [
    { id: 'overview',  label: 'OVERVIEW',       icon: '🎛️' },
    { id: 'radar',     label: '3D RADAR',       icon: '🛰️' },
    { id: 'control',   label: 'MISSION CONTROL', icon: '🎮' },
    { id: 'analytics', label: 'ANALYTICS',      icon: '📈' },
    { id: 'fairness',  label: 'FAIRNESS',       icon: '⚖️' },
    { id: 'arena',     label: 'ARENA',          icon: '🏆' },
  ];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--yellow)', color: 'var(--black)' }}>

      {/* ══════════════════════════════════════════════════════
          HERO BANNER & HEADER
          ══════════════════════════════════════════════════════ */}
      <header style={{ background: 'var(--yellow)', borderBottom: '4px solid var(--black)', padding: '24px 36px 18px' }}>
        <div style={{ maxWidth: 1720, margin: '0 auto', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 20 }}>
          
          {/* Brand */}
          <div>
            <p className="mono" style={{ fontSize: '0.74rem', letterSpacing: '0.14em', fontWeight: 800, textTransform: 'uppercase', marginBottom: 6, opacity: 0.7 }}>
              AI TRAFFIC CONTROL SYSTEM ↓ LIVE SUMO MICROSCOPIC SIMULATION
            </p>
            <h1 className="bebas" style={{ fontSize: 'clamp(56px, 8vw, 110px)', lineHeight: 0.9, letterSpacing: '-0.01em', color: 'var(--black)', margin: 0 }}>
              TRAFFIC<span style={{ color: 'var(--pink)', WebkitTextStroke: '2px var(--black)' }}>MIND</span>
            </h1>
          </div>

          {/* Right Status Block */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-end', paddingTop: 8 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {/* Status pill */}
              <div className="live-pill" style={{ background: isRunning ? 'var(--lime)' : 'var(--white)' }}>
                <span className="live-dot" style={{ background: isRunning ? 'var(--black)' : '#aaa' }} />
                <span className="mono" style={{ fontSize: '0.72rem', letterSpacing: '0.08em' }}>
                  {isRunning ? 'SIM STREAMING' : 'ENGINE IDLE'}
                </span>
              </div>

              {/* Clock */}
              <div style={{ background: 'var(--black)', color: 'var(--yellow)', border: '3px solid var(--black)', borderRadius: 999, padding: '7px 20px', fontFamily: "'Space Mono',monospace", fontWeight: 800, fontSize: '1rem', boxShadow: '4px 4px 0px 0px var(--black)' }}>
                {fmt(currentStep)} / {fmt(duration)}
              </div>
            </div>

            {/* Quick Action Button in Header */}
            <div style={{ display: 'flex', gap: 10 }}>
              {!isRunning ? (
                <button
                  className="brutalist-btn lime"
                  onClick={handleStartSim}
                  style={{ padding: '8px 24px', fontSize: '0.9rem' }}
                >
                  ▶ START
                </button>
              ) : (
                <button
                  className="brutalist-btn pink"
                  onClick={handleStopSim}
                  style={{ padding: '8px 24px', fontSize: '0.9rem' }}
                >
                  ■ ABORT
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ══════════════════════════════════════════════════════
          NAVBAR TABS (STICKY TAB BAR)
          ══════════════════════════════════════════════════════ */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 90,
          background: 'var(--yellow)',
          borderBottom: '4px solid var(--black)',
          padding: '12px 36px',
          boxShadow: '0 4px 0px rgba(0,0,0,0.15)',
        }}
      >
        <div style={{ maxWidth: 1720, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
          {/* Tabs */}
          <nav style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {tabs.map(t => {
              const active = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`brutalist-tab ${active ? 'active' : ''}`}
                >
                  <span>{t.icon}</span>
                  <span>{t.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Active Controller Tag */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="mono" style={{ fontSize: '0.68rem', fontWeight: 800, opacity: 0.65 }}>CONTROLLER:</span>
            <span className="mono" style={{ fontSize: '0.74rem', fontWeight: 800, background: 'var(--black)', color: 'var(--yellow)', padding: '4px 12px', borderRadius: 999, border: '2px solid var(--black)', boxShadow: '2px 2px 0 var(--black)' }}>
              {selectedController.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      {/* ── Marquee Bands ──────────────────────────────────── */}
      <Marquee text="TRAFFICMIND AI REINFORCEMENT LEARNING SIMULATION" bg="var(--pink)" color="var(--yellow)" />
      <Marquee text="ADAPTIVE MAX-PRESSURE · DEEP PPO NEURAL POLICY · DETERMINISTIC BASELINE" bg="var(--black)" color="var(--lime)" slow reverse />

      {/* ══════════════════════════════════════════════════════
          MAIN CONTENT (SWITCHED PER TAB)
          ══════════════════════════════════════════════════════ */}
      <main style={{ flex: 1, padding: '28px 36px 64px', maxWidth: 1720, margin: '0 auto', width: '100%' }}>
        <div ref={tabContentRef}>

          {/* ──────────────────────────────────────────────────
              TAB 1: OVERVIEW
              ────────────────────────────────────────────────── */}
          {activeTab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 26 }}>
              {/* Telemetry KPI Cards */}
              <TelemetryCards
                avgWait={avgWait}
                totalQueue={totalQueue}
                throughput={throughput}
                activeVehicles={activeVehicles}
                maxWait={maxWait}
                currentPhase={currentPhase}
                manualOverrideActive={manualOverrideActive}
              />

              {/* Grid: 3D/2D Radar on Left, Quick Control & Fairness on Right */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 26 }}>
                {/* Radar Column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span className="bebas" style={{ fontSize: '1.8rem', letterSpacing: '0.04em', color: 'var(--black)' }}>
                      INTERSECTION RADAR FEED
                    </span>
                    {/* 3D vs 2D Toggle */}
                    <div style={{ display: 'flex', background: 'var(--black)', border: '3px solid var(--black)', borderRadius: 999, overflow: 'hidden', boxShadow: '3px 3px 0 var(--black)' }}>
                      {(['3d','2d'] as const).map(m => (
                        <button
                          key={m}
                          onClick={() => setViewMode(m)}
                          style={{
                            padding: '6px 18px',
                            border: 'none',
                            cursor: 'pointer',
                            fontFamily: "'Space Mono',monospace",
                            fontWeight: 800,
                            fontSize: '0.78rem',
                            background: viewMode === m ? 'var(--lime)' : 'transparent',
                            color: viewMode === m ? 'var(--black)' : 'var(--yellow)',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          {m.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="radar-brutalist-frame" style={{ height: 490 }}>
                    {viewMode === '3d'
                      ? <Viewport3D vehicles={vehicles} tlsState={tlsState} currentPhase={currentPhase} />
                      : <Canvas2DRadar vehicles={vehicles} tlsState={tlsState} currentPhase={currentPhase} />
                    }
                  </div>
                </div>

                {/* Right Column: Mission Control & Spatial Balance */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  <ControlDeck
                    compact
                    isRunning={isRunning}
                    selectedController={selectedController}
                    onSelectController={setSelectedController}
                    selectedScenario={selectedScenario}
                    onSelectScenario={setSelectedScenario}
                    duration={duration}
                    onChangeDuration={setDuration}
                    speed={speed}
                    onChangeSpeed={handleSpeedChange}
                    onStartSim={handleStartSim}
                    onStopSim={handleStopSim}
                    onOpenBenchmark={() => setActiveTab('arena')}
                    onInjectEmergency={handleInjectEmergency}
                    onOverrideSignal={handleOverrideSignal}
                  />

                  <ApproachFairness queues={queues} waits={waits} />
                </div>
              </div>

              {/* Live Dynamics Chart Row */}
              <LiveChart history={telemetryHistory} />
            </div>
          )}

          {/* ──────────────────────────────────────────────────
              TAB 2: 3D RADAR FEED
              ────────────────────────────────────────────────── */}
          {activeTab === 'radar' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
                <div>
                  <div className="mono" style={{ fontSize: '0.68rem', letterSpacing: '0.12em', fontWeight: 800, opacity: 0.65 }}>
                    ECLIPSE SUMO MICROSCOPIC EMULATION
                  </div>
                  <h2 className="bebas" style={{ fontSize: '2.8rem', letterSpacing: '0.04em', lineHeight: 1, color: 'var(--black)' }}>
                    FULL-SCALE RADAR VIEWPORT
                  </h2>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  {/* Mode selector */}
                  <div style={{ display: 'flex', background: 'var(--black)', border: '3px solid var(--black)', borderRadius: 999, overflow: 'hidden', boxShadow: '4px 4px 0 var(--black)' }}>
                    {(['3d','2d'] as const).map(m => (
                      <button
                        key={m}
                        onClick={() => setViewMode(m)}
                        style={{
                          padding: '8px 22px',
                          border: 'none',
                          cursor: 'pointer',
                          fontFamily: "'Space Mono',monospace",
                          fontWeight: 800,
                          fontSize: '0.82rem',
                          background: viewMode === m ? 'var(--lime)' : 'transparent',
                          color: viewMode === m ? 'var(--black)' : 'var(--yellow)',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {m === '3d' ? '3D PERSPECTIVE' : '2D RADAR'}
                      </button>
                    ))}
                  </div>

                  <div className="live-pill" style={{ background: 'var(--white)' }}>
                    <span style={{ fontSize: '1rem' }}>🚗</span>
                    <span className="mono" style={{ fontSize: '0.78rem' }}>
                      {vehicles.length} VEHICLES ACTIVE
                    </span>
                  </div>
                </div>
              </div>

              {/* Expanded Radar Frame */}
              <div className="radar-brutalist-frame" style={{ height: 640, width: '100%' }}>
                {viewMode === '3d'
                  ? <Viewport3D vehicles={vehicles} tlsState={tlsState} currentPhase={currentPhase} />
                  : <Canvas2DRadar vehicles={vehicles} tlsState={tlsState} currentPhase={currentPhase} />
                }
              </div>

              {/* Fast Emergency Strip */}
              <div className="brutalist-card" style={{ padding: '18px 26px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14, background: 'var(--white)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: '1.4rem' }}>🚑</span>
                  <div>
                    <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 800, fontSize: '0.95rem', color: 'var(--black)' }}>
                      QUICK EMERGENCY DISPATCH
                    </div>
                    <div className="mono" style={{ fontSize: '0.7rem', opacity: 0.65, fontWeight: 700 }}>
                      SPAWN HIGHEST-PRIORITY SIREN VEHICLE DIRECTLY INTO INTERSECTION
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  {(['N','S','E','W'] as const).map(arm => (
                    <button
                      key={arm}
                      disabled={!isRunning}
                      onClick={() => handleInjectEmergency(arm)}
                      className="brutalist-btn pink"
                      style={{ padding: '9px 20px', fontSize: '0.82rem' }}
                    >
                      SPAWN → {arm}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ──────────────────────────────────────────────────
              TAB 3: MISSION CONTROL
              ────────────────────────────────────────────────── */}
          {activeTab === 'control' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1.25fr 1fr', gap: 26 }}>
              {/* Full Control Deck */}
              <ControlDeck
                isRunning={isRunning}
                selectedController={selectedController}
                onSelectController={setSelectedController}
                selectedScenario={selectedScenario}
                onSelectScenario={setSelectedScenario}
                duration={duration}
                onChangeDuration={setDuration}
                speed={speed}
                onChangeSpeed={handleSpeedChange}
                onStartSim={handleStartSim}
                onStopSim={handleStopSim}
                onOpenBenchmark={() => setActiveTab('arena')}
                onInjectEmergency={handleInjectEmergency}
                onOverrideSignal={handleOverrideSignal}
              />

              {/* Details & Live Signal State */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                {/* Controller Explanation */}
                <div className="brutalist-card" style={{ padding: 26, background: 'var(--white)' }}>
                  <div className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.15em', opacity: 0.6, fontWeight: 800, marginBottom: 4 }}>
                    MATHEMATICAL FOUNDATION
                  </div>
                  <h3 className="bebas" style={{ fontSize: '2.2rem', letterSpacing: '0.04em', color: 'var(--black)', marginBottom: 14 }}>
                    ALGORITHM SPECIFICATION
                  </h3>

                  {selectedController === 'adaptive' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.9rem', color: 'var(--black)', lineHeight: 1.6 }}>
                      <p>
                        <strong>Adaptive Max-Pressure AI:</strong> Evaluates differential queue pressure <code className="mono" style={{ background: 'var(--yellow)', border: '2px solid var(--black)', padding: '2px 8px', borderRadius: 6, fontWeight: 800 }}>W(p) = Σ q_in - Σ q_out</code> continuously.
                      </p>
                      <p>
                        Features an <strong>Anti-Starvation Multiplier</strong> that escalates green probability linearly for waiting phases, preventing minor corridors from starvation during heavy main artery throughput.
                      </p>
                    </div>
                  )}

                  {selectedController === 'rl' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.9rem', color: 'var(--black)', lineHeight: 1.6 }}>
                      <p>
                        <strong>Deep PPO Reinforcement Learning:</strong> Multi-layer perceptron neural policy trained with Proximal Policy Optimization against microscopic SUMO state tensors.
                      </p>
                      <p>
                        Optimizes multi-objective reward <code className="mono" style={{ background: 'var(--purple)', color: '#fff', border: '2px solid var(--black)', padding: '2px 8px', borderRadius: 6, fontWeight: 800 }}>R = - (α·Delay + β·Queue + γ·EmergencyWait)</code>.
                      </p>
                    </div>
                  )}

                  {selectedController === 'fixed' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.9rem', color: 'var(--black)', lineHeight: 1.6 }}>
                      <p>
                        <strong>Fixed-Time Cyclic Baseline:</strong> Standard deterministic 35-second phase rotation. Does not react to incoming queues or emergency vehicles.
                      </p>
                    </div>
                  )}
                </div>

                {/* Signal Phase HUD */}
                <div className="brutalist-card" style={{ padding: 26, background: 'var(--white)' }}>
                  <div className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.15em', opacity: 0.6, fontWeight: 800, marginBottom: 4 }}>
                    INTERSECTION SIGNAL HUD
                  </div>
                  <h3 className="bebas" style={{ fontSize: '2.2rem', letterSpacing: '0.04em', color: 'var(--black)', marginBottom: 14 }}>
                    ACTIVE SIGNAL PHASE
                  </h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                    <div className="live-dot" style={{ width: 18, height: 18 }} />
                    <span className="mono" style={{ fontSize: '0.95rem', fontWeight: 800 }}>
                      PHASE #{currentPhase}: {currentPhase === 0 ? 'NORTH-SOUTH GREEN' : currentPhase === 1 ? 'NORTH-SOUTH YELLOW' : currentPhase === 2 ? 'EAST-WEST GREEN' : 'EAST-WEST YELLOW'}
                    </span>
                  </div>
                  <div className="mono" style={{ fontSize: '0.8rem', background: 'var(--black)', color: 'var(--yellow)', padding: '12px 16px', borderRadius: 10, border: '3px solid var(--black)', boxShadow: '4px 4px 0 var(--black)' }}>
                    SUMO BITSTRING: <strong>{tlsState}</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ──────────────────────────────────────────────────
              TAB 4: LIVE ANALYTICS
              ────────────────────────────────────────────────── */}
          {activeTab === 'analytics' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 26 }}>
              <TelemetryCards
                avgWait={avgWait}
                totalQueue={totalQueue}
                throughput={throughput}
                activeVehicles={activeVehicles}
                maxWait={maxWait}
                currentPhase={currentPhase}
                manualOverrideActive={manualOverrideActive}
              />

              <LiveChart history={telemetryHistory} />

              {/* Completion Summary Card */}
              {latestSummary && (
                <div className="brutalist-card lime" style={{ padding: 28 }}>
                  <div className="bebas" style={{ fontSize: '2.4rem', letterSpacing: '0.04em', marginBottom: 16 }}>
                    🏁 SIMULATION RUN COMPLETE
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
                    {[
                      { label: 'COMPLETION RATE', value: `${latestSummary.completion_rate?.toFixed(1)}%`, bg: 'var(--purple)', color: '#fff' },
                      { label: 'DISCHARGE CAPACITY', value: `${latestSummary.throughput_per_minute?.toFixed(1)}/min`, bg: 'var(--pink)', color: '#fff' },
                      { label: 'AVERAGE LATENCY', value: `${latestSummary.avg_waiting_time_sec?.toFixed(1)}s`, bg: 'var(--black)', color: 'var(--yellow)' },
                      { label: 'PEAK QUEUE', value: `${latestSummary.max_queue_length} veh`, bg: 'var(--white)', color: 'var(--black)' },
                    ].map(s => (
                      <div key={s.label} style={{ background: s.bg, color: s.color, border: '3px solid var(--black)', borderRadius: 12, padding: '16px', boxShadow: '4px 4px 0 var(--black)', textAlign: 'center' }}>
                        <div className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.1em', opacity: 0.8, marginBottom: 4, fontWeight: 700 }}>{s.label}</div>
                        <div className="bebas" style={{ fontSize: '2.2rem', lineHeight: 1 }}>{s.value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ──────────────────────────────────────────────────
              TAB 5: DIRECTIONAL FAIRNESS
              ────────────────────────────────────────────────── */}
          {activeTab === 'fairness' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 26 }}>
              <ApproachFairness queues={queues} waits={waits} />

              {/* Detailed Approach Breakdown Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
                {[
                  { arm: 'NORTH (N)', queue: queues.N || 0, wait: waits.N || 0, desc: 'North Artery Boulevard', bg: 'var(--yellow)' },
                  { arm: 'SOUTH (S)', queue: queues.S || 0, wait: waits.S || 0, desc: 'South Highway Connector', bg: 'var(--lime)' },
                  { arm: 'EAST (E)',  queue: queues.E || 0, wait: waits.E || 0, desc: 'East Commercial Avenue', bg: 'var(--purple)', color: '#fff' },
                  { arm: 'WEST (W)',  queue: queues.W || 0, wait: waits.W || 0, desc: 'West Residential Corridor', bg: 'var(--orange)', color: '#fff' },
                ].map(item => (
                  <div key={item.arm} className="brutalist-card" style={{ padding: 22, background: item.bg, color: item.color || 'var(--black)' }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span className="bebas" style={{ fontSize: '1.8rem' }}>{item.arm}</span>
                      <span className="mono" style={{ fontSize: '0.74rem', fontWeight: 800 }}>
                        {item.wait > 20 ? '⚠ CONGESTED' : '● BALANCED'}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.82rem', fontWeight: 600, opacity: 0.8, marginBottom: 14 }}>{item.desc}</p>
                    <div style={{ display: 'flex', gap: 12 }}>
                      <div style={{ flex: 1, background: 'rgba(0,0,0,0.12)', border: '2px solid var(--black)', borderRadius: 10, padding: '10px 14px' }}>
                        <div className="mono" style={{ fontSize: '0.62rem', fontWeight: 700, opacity: 0.7 }}>QUEUE</div>
                        <div className="bebas" style={{ fontSize: '2rem', lineHeight: 1 }}>{item.queue}</div>
                      </div>
                      <div style={{ flex: 1, background: 'rgba(0,0,0,0.12)', border: '2px solid var(--black)', borderRadius: 10, padding: '10px 14px' }}>
                        <div className="mono" style={{ fontSize: '0.62rem', fontWeight: 700, opacity: 0.7 }}>WAIT</div>
                        <div className="bebas" style={{ fontSize: '2rem', lineHeight: 1 }}>{item.wait.toFixed(1)}s</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ──────────────────────────────────────────────────
              TAB 6: BENCHMARK ARENA
              ────────────────────────────────────────────────── */}
          {activeTab === 'arena' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div className="brutalist-card yellow" style={{ padding: 36 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 16 }}>
                  <div>
                    <div className="mono" style={{ fontSize: '0.68rem', letterSpacing: '0.15em', fontWeight: 800, opacity: 0.65, marginBottom: 4 }}>
                      HEAD-TO-HEAD CONTROLLER EVALUATION
                    </div>
                    <h2 className="bebas" style={{ fontSize: '3.4rem', letterSpacing: '0.03em', lineHeight: 0.95, color: 'var(--black)' }}>
                      BENCHMARK <span style={{ color: 'var(--pink)', WebkitTextStroke: '2px var(--black)' }}>ARENA</span>
                    </h2>
                    <p style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 600, color: 'rgba(0,0,0,0.7)', fontSize: '1rem', marginTop: 10, maxWidth: 640 }}>
                      Run automated Monte Carlo simulations across all 3 controllers under identical pseudo-random seeds across Normal, Asymmetric Artery, and Rush Hour conditions.
                    </p>
                  </div>

                  <button
                    onClick={() => setIsBenchmarkOpen(true)}
                    className="brutalist-btn orange"
                    style={{ fontSize: '1.1rem', padding: '16px 36px', boxShadow: '6px 6px 0 var(--black)' }}
                  >
                    🔥 LAUNCH TOURNAMENT ARENA
                  </button>
                </div>

                {/* Feature cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
                  {[
                    { title: 'DETERMINISTIC EVALUATION', desc: 'Controlled seed=42 ensuring vehicle departure sequences are identical for 100% fair comparison.', emoji: '🎲' },
                    { title: 'MULTI-OBJECTIVE METRICS', desc: 'Measures queue length, waiting times, stops per vehicle, and total throughput per minute.', emoji: '📊' },
                    { title: 'LATENCY REDUCTION REPORT', desc: 'Computes exact percentage reduction in driver delay compared to standard fixed time cycles.', emoji: '📉' },
                  ].map(f => (
                    <div key={f.title} style={{ background: 'var(--white)', border: '3px solid var(--black)', borderRadius: 14, padding: 18, boxShadow: '4px 4px 0 var(--black)' }}>
                      <div style={{ fontSize: '1.8rem', marginBottom: 8 }}>{f.emoji}</div>
                      <div className="mono" style={{ fontSize: '0.78rem', fontWeight: 800, color: 'var(--black)', marginBottom: 6 }}>{f.title}</div>
                      <div style={{ fontSize: '0.82rem', fontWeight: 500, color: 'rgba(0,0,0,0.7)', lineHeight: 1.5 }}>{f.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

        </div>
      </main>

      {/* ── Marquee Footer ─────────────────────────────────── */}
      <Marquee text="FIXED-TIME · ADAPTIVE PRESSURE · DEEP PPO REINFORCEMENT LEARNING · SUMO TRACI · FASTAPI" bg="var(--purple)" color="var(--white)" />
      <footer style={{ background: 'var(--black)', color: 'var(--yellow)', padding: '18px 36px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: "'Space Mono',monospace", fontSize: '0.75rem', borderTop: '4px solid var(--black)', flexWrap: 'wrap', gap: 12 }}>
        <span>TRAFFICMIND © 2026 — AI URBAN SIGNAL CONTROL</span>
        <span style={{ opacity: 0.6 }}>POWERED BY ECLIPSE SUMO · PPO · FASTAPI SSE</span>
      </footer>

      {/* Benchmark Modal */}
      <BenchmarkModal isOpen={isBenchmarkOpen} onClose={() => setIsBenchmarkOpen(false)} />
    </div>
  );
};

export default App;
