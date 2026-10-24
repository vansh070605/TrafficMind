import React, { useState } from 'react';

interface ControlDeckProps {
  isRunning:           boolean;
  selectedController:  string;
  onSelectController:  (c: string) => void;
  selectedScenario:    string;
  onSelectScenario:    (s: string) => void;
  duration:            number;
  onChangeDuration:    (d: number) => void;
  speed:               number;
  onChangeSpeed:       (s: number) => void;
  onStartSim:          () => void;
  onStopSim:           () => void;
  onOpenBenchmark:     () => void;
  onInjectEmergency:   (origin: string) => void;
  onOverrideSignal:    (phase: number) => void;
  compact?:            boolean;
}

const CONTROLLERS = [
  { id: 'adaptive', name: 'ADAPTIVE AI', desc: 'Queue-pressure max-weight + anti-starvation', emoji: '⚡', bg: 'var(--yellow)', color: 'var(--black)' },
  { id: 'rl',       name: 'DEEP PPO',   desc: 'Trained neural policy with actor-critic',     emoji: '🧠', bg: 'var(--purple)', color: '#FFFFFF' },
  { id: 'fixed',    name: 'FIXED TIME', desc: 'Deterministic 35s static split cycle',        emoji: '⏱', bg: 'var(--white)',  color: 'var(--black)' },
];

const SCENARIOS = [
  { id: 'normal',            name: 'NORMAL' },
  { id: 'rush_hour',         name: 'RUSH HOUR' },
  { id: 'unbalanced',        name: 'ASYM N-S' },
  { id: 'surge',             name: 'SURGE' },
  { id: 'unseen_evaluation', name: 'UNSEEN' },
];

export const ControlDeck: React.FC<ControlDeckProps> = ({
  isRunning, selectedController, onSelectController,
  selectedScenario, onSelectScenario,
  duration, onChangeDuration, speed, onChangeSpeed,
  onStartSim, onStopSim, onOpenBenchmark,
  onInjectEmergency, onOverrideSignal,
  compact = false,
}) => {
  const [injectOrigin, setInjectOrigin] = useState<'N'|'S'|'E'|'W'>('N');

  return (
    <div className="brutalist-card" style={{ padding: compact ? '20px' : '26px', background: 'var(--off-white)', color: 'var(--black)', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Title */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '3px dashed rgba(0,0,0,0.15)', paddingBottom: 12 }}>
        <div>
          <div className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.15em', color: 'var(--black)', opacity: 0.6, marginBottom: 2, fontWeight: 700 }}>
            SIGNAL CONTROLLER CONFIG
          </div>
          <h2 className="bebas" style={{ fontSize: '2.4rem', letterSpacing: '0.04em', lineHeight: 1, color: 'var(--black)' }}>
            MISSION CONTROL
          </h2>
        </div>
        <div className={`live-pill ${isRunning ? '' : 'opacity-70'}`} style={{ background: isRunning ? 'var(--lime)' : 'var(--white)' }}>
          <span className="live-dot" style={{ background: isRunning ? 'var(--black)' : '#aaa' }} />
          <span className="mono" style={{ fontSize: '0.7rem' }}>
            {isRunning ? 'DISPATCH LIVE' : 'ENGINE READY'}
          </span>
        </div>
      </div>

      {/* ── Controller Selector ─────────────────────────────── */}
      <div>
        <div className="mono" style={{ fontSize: '0.68rem', letterSpacing: '0.12em', color: 'var(--black)', opacity: 0.65, marginBottom: 8, fontWeight: 800 }}>
          CONTROL PARADIGM
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {CONTROLLERS.map(c => {
            const active = selectedController === c.id;
            return (
              <button
                key={c.id}
                onClick={() => onSelectController(c.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                  padding: compact ? '10px 14px' : '12px 18px',
                  borderRadius: 14,
                  cursor: 'pointer',
                  border: '3px solid var(--black)',
                  background: active ? c.bg : 'var(--white)',
                  color: active ? c.color : 'var(--black)',
                  boxShadow: active ? '5px 5px 0px 0px var(--black)' : '2px 2px 0px 0px var(--black)',
                  transform: active ? 'translate(-2px, -2px)' : 'none',
                  transition: 'all 0.18s cubic-bezier(0.34, 1.56, 0.64, 1)',
                  textAlign: 'left',
                }}
              >
                <span style={{ fontSize: '1.4rem' }}>{c.emoji}</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1 }}>
                  <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 800, fontSize: '0.92rem' }}>
                    {c.name}
                  </span>
                  <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: '0.72rem', opacity: 0.75, fontWeight: 600 }}>
                    {c.desc}
                  </span>
                </div>
                {active && (
                  <span className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.1em', fontWeight: 800, padding: '3px 8px', borderRadius: 999, border: '2px solid var(--black)', background: 'var(--black)', color: 'var(--yellow)' }}>
                    ACTIVE
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Scenario Selection ──────────────────────────────── */}
      <div>
        <div className="mono" style={{ fontSize: '0.68rem', letterSpacing: '0.12em', color: 'var(--black)', opacity: 0.65, marginBottom: 8, fontWeight: 800 }}>
          TRAFFIC DEMAND SCENARIO
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {SCENARIOS.map(s => {
            const active = selectedScenario === s.id;
            return (
              <button
                key={s.id}
                onClick={() => onSelectScenario(s.id)}
                style={{
                  padding: '7px 16px',
                  borderRadius: 999,
                  cursor: 'pointer',
                  border: '3px solid var(--black)',
                  background: active ? 'var(--pink)' : 'var(--white)',
                  color: active ? '#FFFFFF' : 'var(--black)',
                  boxShadow: active ? '4px 4px 0px 0px var(--black)' : '2px 2px 0px 0px var(--black)',
                  transform: active ? 'translate(-2px, -2px)' : 'none',
                  fontFamily: "'Space Mono', monospace",
                  fontWeight: 800,
                  fontSize: '0.72rem',
                  letterSpacing: '0.06em',
                  transition: 'all 0.15s ease',
                }}
              >
                {s.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Sliders for Duration & Speed ────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, background: 'var(--black)', borderRadius: 14, padding: '16px 18px', border: '3px solid var(--black)', boxShadow: '5px 5px 0px 0px var(--black)' }}>
        {[
          { label: 'DURATION', value: `${duration}s`, min: 30, max: 600, step: 30, val: duration, onChange: onChangeDuration },
          { label: 'SIM SPEED', value: `${speed.toFixed(1)}×`, min: 0.2, max: 2.5, step: 0.1, val: speed, onChange: onChangeSpeed },
        ].map(s => (
          <div key={s.label}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
              <span className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.7)', fontWeight: 700 }}>{s.label}</span>
              <span className="bebas" style={{ fontSize: '1.2rem', color: 'var(--yellow)', letterSpacing: '0.04em' }}>{s.value}</span>
            </div>
            <input
              type="range"
              min={s.min}
              max={s.max}
              step={s.step}
              value={s.val}
              onChange={e => s.onChange(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--lime)' }}
            />
          </div>
        ))}
      </div>

      {/* ── Action Buttons ──────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button
          className="brutalist-btn lime"
          disabled={isRunning}
          onClick={onStartSim}
          style={{ flex: 1, minWidth: 140, fontSize: '1.05rem', padding: '14px 24px' }}
        >
          <span>▶</span> START
        </button>

        <button
          className="brutalist-btn pink"
          disabled={!isRunning}
          onClick={onStopSim}
          style={{ flex: 1, minWidth: 130, fontSize: '1.05rem', padding: '14px 24px' }}
        >
          <span>■</span> ABORT
        </button>

        <button
          className="brutalist-btn orange"
          onClick={onOpenBenchmark}
          style={{ padding: '14px 22px' }}
        >
          <span>🔥</span> ARENA
        </button>
      </div>

      {/* ── Live Interventions Deck ─────────────────────────── */}
      <div style={{ borderTop: '3px dashed rgba(0,0,0,0.15)', paddingTop: 18 }}>
        <div className="bebas" style={{ fontSize: '1.5rem', letterSpacing: '0.04em', color: 'var(--black)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--pink)' }}>⚠</span> LIVE INTERVENTIONS
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : '1fr 1fr', gap: 12 }}>
          {/* Dispatch Ambulance */}
          <div style={{ background: 'var(--white)', border: '3px solid var(--black)', borderRadius: 12, padding: 14, boxShadow: '4px 4px 0px 0px var(--black)' }}>
            <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 800, fontSize: '0.85rem', color: 'var(--black)', marginBottom: 8 }}>
              🚑 DISPATCH AMBULANCE
            </div>
            <div style={{ display: 'flex', gap: 5, marginBottom: 10 }}>
              {(['N','S','E','W'] as const).map(arm => (
                <button
                  key={arm}
                  onClick={() => setInjectOrigin(arm)}
                  style={{
                    flex: 1,
                    padding: '6px 0',
                    borderRadius: 8,
                    cursor: 'pointer',
                    fontFamily: "'Space Mono',monospace",
                    fontWeight: 800,
                    fontSize: '0.75rem',
                    border: '2px solid var(--black)',
                    background: injectOrigin === arm ? 'var(--pink)' : 'var(--white)',
                    color: injectOrigin === arm ? '#FFFFFF' : 'var(--black)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {arm}
                </button>
              ))}
            </div>
            <button
              className="brutalist-btn pink"
              disabled={!isRunning}
              onClick={() => onInjectEmergency(injectOrigin)}
              style={{ width: '100%', padding: '10px 14px', fontSize: '0.82rem' }}
            >
              SPAWN → {injectOrigin}
            </button>
          </div>

          {/* Force Signal Override */}
          <div style={{ background: 'var(--white)', border: '3px solid var(--black)', borderRadius: 12, padding: 14, boxShadow: '4px 4px 0px 0px var(--black)' }}>
            <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 800, fontSize: '0.85rem', color: 'var(--black)', marginBottom: 8 }}>
              🚦 FORCE SIGNAL PHASE
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button
                className="brutalist-btn lime"
                disabled={!isRunning}
                onClick={() => onOverrideSignal(0)}
                style={{ width: '100%', padding: '10px 14px', fontSize: '0.78rem' }}
              >
                🟢 N-S GREEN (15s)
              </button>
              <button
                className="brutalist-btn cyan"
                disabled={!isRunning}
                onClick={() => onOverrideSignal(2)}
                style={{ width: '100%', padding: '10px 14px', fontSize: '0.78rem' }}
              >
                🟢 E-W GREEN (15s)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
