import React, { useState } from 'react';
import type { BenchmarkRecord } from '../types';

interface BenchmarkModalProps { isOpen: boolean; onClose: () => void; }

const CTRL_STYLE: Record<string, { bg: string; color: string }> = {
  adaptive:  { bg: 'var(--yellow)', color: 'var(--black)' },
  rl:        { bg: 'var(--purple)', color: '#FFFFFF' },
  fixed:     { bg: 'var(--white)',  color: 'var(--black)' },
};

export const BenchmarkModal: React.FC<BenchmarkModalProps> = ({ isOpen, onClose }) => {
  const [loading, setLoading]   = useState(false);
  const [results, setResults]   = useState<BenchmarkRecord[]>([]);
  const [error,   setError]     = useState<string | null>(null);

  if (!isOpen) return null;

  const run = async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch('/api/benchmark', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenarios: ['normal','unbalanced','rush_hour'], duration: 120, seed: 42 }),
      });
      if (!res.ok) throw new Error('Benchmark request failed');
      const data = await res.json();
      setResults(data.results ?? []);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  const cKey = (ctrl: string) => ctrl.toLowerCase().includes('rl') ? 'rl' : ctrl.toLowerCase().includes('adaptive') ? 'adaptive' : 'fixed';

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 920,
          maxHeight: '88vh',
          overflow: 'auto',
          background: 'var(--yellow)',
          border: '4px solid var(--black)',
          borderRadius: 20,
          boxShadow: '12px 12px 0px 0px var(--black)',
          padding: 32,
          position: 'relative',
          color: 'var(--black)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, borderBottom: '3px solid var(--black)', paddingBottom: 16 }}>
          <div>
            <div className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.15em', opacity: 0.6, marginBottom: 4, fontWeight: 700 }}>
              HEAD-TO-HEAD SHOOTOUT
            </div>
            <h2 className="bebas" style={{ fontSize: '3rem', letterSpacing: '0.03em', lineHeight: 0.95, color: 'var(--black)' }}>
              BENCHMARK <span style={{ color: 'var(--pink)', WebkitTextStroke: '1.5px var(--black)' }}>ARENA</span>
            </h2>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 44,
              height: 44,
              border: '3px solid var(--black)',
              borderRadius: 999,
              background: 'var(--black)',
              color: 'var(--yellow)',
              fontFamily: "'Space Grotesk',sans-serif",
              fontWeight: 800,
              fontSize: '1.2rem',
              cursor: 'pointer',
              boxShadow: '3px 3px 0 var(--black)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ✕
          </button>
        </div>

        {/* Empty state */}
        {results.length === 0 && !loading && !error && (
          <div style={{ textAlign: 'center', padding: '48px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
            <div className="bebas" style={{ fontSize: '4.8rem', opacity: 0.15, lineHeight: 0.9, color: 'var(--black)' }}>
              FIXED vs ADAPTIVE vs PPO
            </div>
            <p style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 600, maxWidth: 460, color: 'rgba(0,0,0,0.7)', lineHeight: 1.5, fontSize: '1rem' }}>
              Pit all three controllers head-to-head under identical stochastic traffic loads across <strong style={{ color: 'var(--black)' }}>Normal</strong>, <strong style={{ color: 'var(--black)' }}>Unbalanced Artery</strong>, and <strong style={{ color: 'var(--black)' }}>Rush Hour</strong> demand profiles.
            </p>
            <button
              onClick={run}
              className="brutalist-btn orange"
              style={{ fontSize: '1.1rem', padding: '16px 42px', boxShadow: '6px 6px 0 var(--black)' }}
            >
              🔥 LAUNCH BATTLE
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{ textAlign: 'center', padding: '56px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
            <div className="live-dot" style={{ width: 28, height: 28 }} />
            <div className="bebas" style={{ fontSize: '2.4rem', letterSpacing: '0.04em', color: 'var(--black)' }}>
              RUNNING MICRO-SIMULATIONS...
            </div>
            <p className="mono" style={{ fontSize: '0.8rem', color: 'rgba(0,0,0,0.6)', fontWeight: 700 }}>
              Executing 3 controllers × 3 traffic scenarios (9 runs)
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ background: 'var(--pink)', color: '#FFFFFF', border: '3px solid var(--black)', borderRadius: 12, padding: '16px 20px', marginBottom: 20, boxShadow: '4px 4px 0 var(--black)', fontWeight: 700 }}>
            {error}
          </div>
        )}

        {/* Results Table */}
        {results.length > 0 && (
          <div>
            <div style={{ overflowX: 'auto', borderRadius: 14, border: '3px solid var(--black)', background: 'var(--white)', boxShadow: '6px 6px 0 var(--black)', marginBottom: 20 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontFamily: "'Space Grotesk',sans-serif", fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ background: 'var(--black)', color: 'var(--yellow)', borderBottom: '3px solid var(--black)' }}>
                    <th style={{ padding: '14px 18px', fontWeight: 800 }}>SCENARIO</th>
                    <th style={{ padding: '14px 18px', fontWeight: 800 }}>CONTROLLER</th>
                    <th style={{ padding: '14px 18px', fontWeight: 800 }}>AVG WAIT TIME</th>
                    <th style={{ padding: '14px 18px', fontWeight: 800 }}>AVG QUEUE</th>
                    <th style={{ padding: '14px 18px', fontWeight: 800 }}>THROUGHPUT</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => {
                    const k = cKey(r.controller);
                    const cs = CTRL_STYLE[k] || CTRL_STYLE.fixed;
                    return (
                      <tr key={i} style={{ borderBottom: '2px solid var(--black)', background: i % 2 === 0 ? 'var(--white)' : 'var(--off-white)' }}>
                        <td style={{ padding: '14px 18px', fontWeight: 800, color: 'var(--black)', textTransform: 'uppercase' }}>
                          {r.scenario}
                        </td>
                        <td style={{ padding: '14px 18px' }}>
                          <span style={{ background: cs.bg, color: cs.color, border: '2px solid var(--black)', borderRadius: 999, padding: '4px 12px', fontWeight: 800, fontSize: '0.72rem' }}>
                            {r.controller.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ padding: '14px 18px', color: 'var(--pink)', fontWeight: 800, fontFamily: "'Space Mono',monospace" }}>
                          {r.avg_waiting_time_sec?.toFixed(2)}s
                        </td>
                        <td style={{ padding: '14px 18px', color: 'var(--orange)', fontWeight: 800, fontFamily: "'Space Mono',monospace" }}>
                          {r.avg_queue_length?.toFixed(2)} veh
                        </td>
                        <td style={{ padding: '14px 18px', color: 'var(--purple)', fontWeight: 800, fontFamily: "'Space Mono',monospace" }}>
                          {r.throughput_per_minute?.toFixed(1)}/min
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <button
                onClick={run}
                disabled={loading}
                className="brutalist-btn orange"
                style={{ fontSize: '0.95rem', padding: '12px 28px' }}
              >
                🔄 RE-RUN TOURNAMENT
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
