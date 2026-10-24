import React, { useEffect, useRef } from 'react';
import { gsap } from 'gsap';

interface TelemetryCardsProps {
  avgWait:             number;
  totalQueue:          number;
  throughput:          number;
  activeVehicles:      number;
  maxWait:             number;
  currentPhase:        number;
  manualOverrideActive?: boolean;
}

interface CardDef {
  id:    string;
  label: string;
  value: string;
  sub:   string;
  bg:    string;
  color: string;
  emoji: string;
}

export const TelemetryCards: React.FC<TelemetryCardsProps> = ({
  avgWait, totalQueue, throughput, activeVehicles, maxWait, currentPhase, manualOverrideActive
}) => {
  const wrapRef  = useRef<HTMLDivElement>(null);
  const prevVals = useRef<Record<string, string>>({});

  const cards: CardDef[] = [
    {
      id:    'wait',
      label: 'AVG WAIT TIME',
      value: `${avgWait.toFixed(1)}s`,
      sub:   avgWait < 8 ? '● OPTIMAL FLOW' : avgWait < 20 ? '▲ MODERATE' : '⚠ CONGESTED',
      bg:    avgWait < 8 ? 'var(--lime)' : avgWait < 20 ? 'var(--yellow)' : 'var(--pink)',
      color: avgWait < 20 ? 'var(--black)' : '#FFFFFF',
      emoji: '⏱',
    },
    {
      id:    'queue',
      label: 'TOTAL QUEUE',
      value: `${totalQueue}`,
      sub:   'HALTED VEHICLES',
      bg:    'var(--orange)',
      color: '#FFFFFF',
      emoji: '🚗',
    },
    {
      id:    'throughput',
      label: 'THROUGHPUT',
      value: `${throughput.toFixed(1)}`,
      sub:   'VEHICLES / MIN',
      bg:    'var(--purple)',
      color: '#FFFFFF',
      emoji: '⚡',
    },
    {
      id:    'active',
      label: 'ACTIVE VEHICLES',
      value: `${activeVehicles}`,
      sub:   manualOverrideActive ? '🔴 OVERRIDE ON' : `PHASE ${currentPhase} · MAX ${maxWait.toFixed(0)}s`,
      bg:    manualOverrideActive ? 'var(--pink)' : 'var(--black)',
      color: manualOverrideActive ? '#FFFFFF' : 'var(--yellow)',
      emoji: '📡',
    },
  ];

  // Number pop animation
  useEffect(() => {
    if (!wrapRef.current) return;
    cards.forEach(card => {
      if (prevVals.current[card.id] !== card.value) {
        const el = wrapRef.current?.querySelector(`[data-card="${card.id}"] .num-val`);
        if (el) {
          gsap.fromTo(el,
            { scale: 1.3, y: -6 },
            { scale: 1, y: 0, duration: 0.45, ease: 'elastic.out(1, 0.4)' }
          );
        }
        prevVals.current[card.id] = card.value;
      }
    });
  });

  return (
    <div ref={wrapRef} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
      {cards.map(card => (
        <div
          key={card.id}
          data-card={card.id}
          style={{
            background: card.bg,
            color: card.color,
            border: '4px solid var(--black)',
            borderRadius: 16,
            boxShadow: '6px 6px 0px 0px var(--black)',
            padding: '20px 22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
          }}
        >
          {/* Top Label */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span
              className="mono"
              style={{
                fontSize: '0.68rem',
                fontWeight: 700,
                letterSpacing: '0.12em',
                opacity: 0.85,
                textTransform: 'uppercase',
              }}
            >
              {card.label}
            </span>
            <span style={{ fontSize: '1.3rem' }}>{card.emoji}</span>
          </div>

          {/* Big Number */}
          <div className="num-val bebas" style={{ fontSize: '3.4rem', lineHeight: 1, letterSpacing: '0.02em', margin: '4px 0 8px' }}>
            {card.value}
          </div>

          {/* Subtext Pill */}
          <div
            className="mono"
            style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              background: 'rgba(0, 0, 0, 0.18)',
              padding: '4px 10px',
              borderRadius: 999,
              display: 'inline-flex',
              alignSelf: 'flex-start',
              border: '1.5px solid rgba(0, 0, 0, 0.3)',
            }}
          >
            {card.sub}
          </div>
        </div>
      ))}
    </div>
  );
};
