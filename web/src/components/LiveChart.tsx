import React from 'react';
import type { TelemetryFrame } from '../types';

interface LiveChartProps { history: TelemetryFrame[]; }

export const LiveChart: React.FC<LiveChartProps> = ({ history }) => {
  const points = history.slice(-50);

  if (points.length < 2) {
    return (
      <div className="brutalist-card" style={{ height: 260, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 12, padding: 24, background: 'var(--white)', color: 'var(--black)' }}>
        <span className="bebas" style={{ fontSize: '2.5rem', letterSpacing: '0.04em', opacity: 0.2, color: 'var(--black)' }}>
          QUEUE · DELAY · DYNAMICS
        </span>
        <span className="mono" style={{ fontSize: '0.78rem', letterSpacing: '0.1em', opacity: 0.6, color: 'var(--black)' }}>
          Awaiting simulation telemetry stream...
        </span>
      </div>
    );
  }

  const maxQ = Math.max(...points.map(p => p.total_queue ?? 0), 1);
  const maxW = Math.max(...points.map(p => p.waiting_times ? Math.max(...Object.values(p.waiting_times)) : 0), 1);
  const W = 680, H = 180;

  const toXY = (idx: number, val: number, max: number) => ({
    x: (idx / (points.length - 1)) * W,
    y: H - (val / max) * (H - 24) - 12,
  });

  const buildPath = (vals: number[], max: number) => {
    return vals.map((v, i) => {
      const { x, y } = toXY(i, v, max);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  };

  const buildArea = (vals: number[], max: number) => {
    const pathStr = buildPath(vals, max);
    const last = toXY(vals.length - 1, vals[vals.length - 1], max);
    const first = toXY(0, vals[0], max);
    return `${pathStr} L${last.x},${H} L${first.x},${H} Z`;
  };

  const queueVals = points.map(p => p.total_queue ?? 0);
  const waitVals  = points.map(p => p.waiting_times ? Object.values(p.waiting_times).reduce((a,b)=>a+b,0)/4 : 0);
  const peakQ = Math.max(...queueVals);
  const peakW = Math.max(...waitVals);

  return (
    <div className="brutalist-card" style={{ padding: 24, background: 'var(--white)', color: 'var(--black)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div className="mono" style={{ fontSize: '0.65rem', letterSpacing: '0.15em', color: 'var(--black)', opacity: 0.6, marginBottom: 2, fontWeight: 700 }}>
            STREAMING DYNAMICS
          </div>
          <h3 className="bebas" style={{ fontSize: '2rem', letterSpacing: '0.04em', lineHeight: 1, color: 'var(--black)' }}>
            QUEUE &amp; DELAY LIVE
          </h3>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{ width: 14, height: 14, background: '#FF2D78', border: '2px solid var(--black)', borderRadius: 4 }} />
            <span className="mono" style={{ fontSize: '0.72rem', letterSpacing: '0.08em', fontWeight: 800, color: 'var(--black)' }}>
              QUEUE (veh)
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{ width: 14, height: 14, background: '#7B2FFF', border: '2px solid var(--black)', borderRadius: 4 }} />
            <span className="mono" style={{ fontSize: '0.72rem', letterSpacing: '0.08em', fontWeight: 800, color: 'var(--black)' }}>
              AVG WAIT (sec)
            </span>
          </div>
        </div>
      </div>

      {/* SVG Canvas Area */}
      <div style={{ overflowX: 'hidden', borderRadius: 12, border: '3px solid var(--black)', background: '#0A0A0A', padding: '10px 14px' }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', minHeight: 160, display: 'block' }}>
          <defs>
            <linearGradient id="gq-brutal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#FF2D78" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#FF2D78" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="gw-brutal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#7B2FFF" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#7B2FFF" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[H * 0.25, H * 0.5, H * 0.75].map((y, i) => (
            <line key={i} x1={0} y1={y} x2={W} y2={y} stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="4 4" />
          ))}

          {/* Queue area & stroke */}
          <path d={buildArea(queueVals, maxQ)} fill="url(#gq-brutal)" />
          <path d={buildPath(queueVals, maxQ)} fill="none" stroke="#FF2D78" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

          {/* Wait area & stroke */}
          <path d={buildArea(waitVals, maxW)} fill="url(#gw-brutal)" />
          <path d={buildPath(waitVals, maxW)} fill="none" stroke="#7B2FFF" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

          {/* Live tip dot */}
          {(() => {
            const lastQ = toXY(points.length - 1, queueVals[queueVals.length - 1], maxQ);
            return <circle cx={lastQ.x} cy={lastQ.y} r={6} fill="#FF2D78" stroke="var(--black)" strokeWidth={2.5} />;
          })()}
        </svg>
      </div>

      {/* Peak stats footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, flexWrap: 'wrap', gap: 8 }}>
        <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--black)', opacity: 0.65, fontWeight: 700 }}>
          STREAM WINDOW: LAST {points.length}s
        </span>
        <div style={{ display: 'flex', gap: 16 }}>
          <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--black)', fontWeight: 800 }}>
            PEAK QUEUE: <strong style={{ color: '#FF2D78' }}>{peakQ.toFixed(0)} veh</strong>
          </span>
          <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--black)', fontWeight: 800 }}>
            PEAK WAIT: <strong style={{ color: '#7B2FFF' }}>{peakW.toFixed(1)}s</strong>
          </span>
        </div>
      </div>
    </div>
  );
};
