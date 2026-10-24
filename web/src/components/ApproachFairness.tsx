import React, { useRef, useEffect } from 'react';
import { gsap } from 'gsap';

interface ApproachFairnessProps {
  queues: Record<string, number>;
  waits:  Record<string, number>;
}

const ARMS = [
  { key: 'N', name: 'NORTH', color: 'var(--yellow)', text: 'var(--black)' },
  { key: 'S', name: 'SOUTH', color: 'var(--lime)',   text: 'var(--black)' },
  { key: 'E', name: 'EAST',  color: 'var(--purple)', text: '#FFFFFF' },
  { key: 'W', name: 'WEST',  color: 'var(--orange)', text: '#FFFFFF' },
];

export const ApproachFairness: React.FC<ApproachFairnessProps> = ({ queues, waits }) => {
  const barRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const maxQ = Math.max(...Object.values(queues), 1);

  // Compute Jain's Fairness Index
  const qVals = Object.values(queues);
  const sum = qVals.reduce((a, b) => a + b, 0);
  const sumSq = qVals.reduce((a, b) => a + b * b, 0);
  const jainIndex = sum === 0 ? 100 : Math.round(((sum * sum) / (4 * (sumSq || 1))) * 100);

  // Animate bars on queue update
  useEffect(() => {
    ARMS.forEach(arm => {
      const el = barRefs.current.get(arm.key);
      if (!el) return;
      const pct = Math.min(100, Math.round(((queues[arm.key] ?? 0) / maxQ) * 100));
      gsap.to(el, { width: `${pct}%`, duration: 0.45, ease: 'power2.out' });
    });
  }, [queues, maxQ]);

  return (
    <div className="brutalist-card" style={{ padding: 24, background: 'var(--white)', color: 'var(--black)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <div className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.15em', color: 'var(--black)', opacity: 0.6, marginBottom: 2, fontWeight: 700 }}>
            SPATIAL BALANCE &amp; STARVATION METRICS
          </div>
          <h3 className="bebas" style={{ fontSize: '2rem', letterSpacing: '0.04em', lineHeight: 1, color: 'var(--black)' }}>
            DIRECTIONAL FAIRNESS
          </h3>
        </div>

        {/* Fairness Indicator Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--black)', color: 'var(--yellow)', padding: '6px 14px', borderRadius: 999, border: '2px solid var(--black)', boxShadow: '3px 3px 0 var(--black)' }}>
          <span className="mono" style={{ fontSize: '0.7rem', fontWeight: 700 }}>EQUILIBRIUM:</span>
          <span className="mono" style={{ fontSize: '0.82rem', fontWeight: 800 }}>{jainIndex}%</span>
        </div>
      </div>

      {/* Grid of 4 arms */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {ARMS.map(arm => {
          const q = queues[arm.key] ?? 0;
          const w = waits[arm.key]  ?? 0;
          const pct = Math.min(100, Math.round((q / maxQ) * 100));

          return (
            <div
              key={arm.key}
              style={{
                border: '3px solid var(--black)',
                borderRadius: 14,
                padding: '14px 14px 12px',
                boxShadow: '4px 4px 0px 0px var(--black)',
                background: arm.color,
                color: arm.text,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              {/* Arm label + count */}
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                <span className="bebas" style={{ fontSize: '1.6rem', letterSpacing: '0.04em' }}>{arm.name}</span>
                <span className="bebas" style={{ fontSize: '2.2rem', letterSpacing: '-0.01em', lineHeight: 1 }}>{q}</span>
              </div>

              {/* Progress bar */}
              <div style={{ height: 16, borderRadius: 999, border: '2.5px solid var(--black)', background: 'rgba(0,0,0,0.1)', overflow: 'hidden' }}>
                <div
                  ref={el => { if (el) barRefs.current.set(arm.key, el); }}
                  style={{
                    height: '100%',
                    borderRadius: 999,
                    background: 'var(--black)',
                    width: `${pct}%`,
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>

              {/* Wait time */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: '0.62rem', letterSpacing: '0.1em', opacity: 0.8, fontWeight: 700 }}>
                  WAIT PRESSURE
                </span>
                <span
                  className="mono"
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 800,
                    color: w > 20 ? (arm.text === '#FFFFFF' ? '#FFD1DC' : '#990000') : arm.text,
                  }}
                >
                  {w.toFixed(1)}s
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
