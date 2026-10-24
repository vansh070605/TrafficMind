import React, { useEffect, useRef } from 'react';
import type { Vehicle } from '../types';


interface Canvas2DRadarProps {
  vehicles: Vehicle[];
  tlsState: string;
  currentPhase: number;
}

export const Canvas2DRadar: React.FC<Canvas2DRadarProps> = ({ vehicles, tlsState, currentPhase }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const cx = width / 2;
    const cy = height / 2;
    const roadWidth = 80;

    // Clear
    ctx.fillStyle = '#070b16';
    ctx.fillRect(0, 0, width, height);

    // Draw Subtle Cyber Radar Grid
    ctx.strokeStyle = 'rgba(30, 58, 138, 0.2)';
    ctx.lineWidth = 1;
    for (let r = 50; r <= 260; r += 50) {
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Concentric Sweep Line
    const time = Date.now() / 1500;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(time);
    const grad = ctx.createLinearGradient(0, 0, 240, 0);
    grad.addColorStop(0, 'rgba(0, 240, 255, 0.15)');
    grad.addColorStop(1, 'rgba(0, 240, 255, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, 260, 0, Math.PI / 3);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Asphalt Roads
    ctx.fillStyle = '#111827';
    // North-South Road
    ctx.fillRect(cx - roadWidth / 2, 0, roadWidth, height);
    // East-West Road
    ctx.fillRect(0, cy - roadWidth / 2, width, roadWidth);

    // Junction Core
    ctx.fillStyle = '#172033';
    ctx.fillRect(cx - roadWidth / 2, cy - roadWidth / 2, roadWidth, roadWidth);

    // Dashed centerlines
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
    ctx.setLineDash([8, 8]);
    ctx.lineWidth = 2;
    // NS
    ctx.beginPath();
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, cy - roadWidth / 2);
    ctx.moveTo(cx, cy + roadWidth / 2);
    ctx.lineTo(cx, height);
    ctx.stroke();
    // EW
    ctx.beginPath();
    ctx.moveTo(0, cy);
    ctx.lineTo(cx - roadWidth / 2, cy);
    ctx.moveTo(cx + roadWidth / 2, cy);
    ctx.lineTo(width, cy);
    ctx.stroke();
    ctx.setLineDash([]);

    // Stop Lines with Traffic Signal Colors
    const isNSGreen = currentPhase === 0;
    const isNSYellow = currentPhase === 1;
    const isEWGreen = currentPhase === 2;
    const isEWYellow = currentPhase === 3;

    const nsColor = isNSGreen ? '#10b981' : isNSYellow ? '#f59e0b' : '#ef4444';
    const ewColor = isEWGreen ? '#10b981' : isEWYellow ? '#f59e0b' : '#ef4444';

    // North Stop Line
    ctx.strokeStyle = nsColor;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(cx - roadWidth / 2, cy - roadWidth / 2);
    ctx.lineTo(cx, cy - roadWidth / 2);
    ctx.stroke();

    // South Stop Line
    ctx.beginPath();
    ctx.moveTo(cx, cy + roadWidth / 2);
    ctx.lineTo(cx + roadWidth / 2, cy + roadWidth / 2);
    ctx.stroke();

    // West Stop Line
    ctx.strokeStyle = ewColor;
    ctx.beginPath();
    ctx.moveTo(cx - roadWidth / 2, cy);
    ctx.lineTo(cx - roadWidth / 2, cy + roadWidth / 2);
    ctx.stroke();

    // East Stop Line
    ctx.beginPath();
    ctx.moveTo(cx + roadWidth / 2, cy - roadWidth / 2);
    ctx.lineTo(cx + roadWidth / 2, cy);
    ctx.stroke();

    // Draw Vehicles
    vehicles.forEach((v) => {
      // Map SUMO coords around 100, 100 to canvas center
      const px = cx + (v.x - 100) * 2.4;
      const py = cy - (v.y - 100) * 2.4; // inverted y

      ctx.save();
      ctx.translate(px, py);
      ctx.rotate((v.angle * Math.PI) / 180);

      const isEm = v.isEmergency || v.id.includes('EMERGENCY');

      // Vehicle Shadow
      ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
      ctx.fillRect(-6, -11, 14, 24);

      // Vehicle Chassis
      ctx.fillStyle = isEm ? '#f43f5e' : v.wait > 10 ? '#ef4444' : v.speed > 5 ? '#00f0ff' : '#38bdf8';
      ctx.beginPath();
      ctx.roundRect(-5, -10, 10, 20, 3);
      ctx.fill();

      // Windshield
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(-3.5, -4, 7, 5);

      // Headlight beams
      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.beginPath();
      ctx.moveTo(-3, -10);
      ctx.lineTo(-6, -20);
      ctx.lineTo(0, -20);
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(3, -10);
      ctx.lineTo(0, -20);
      ctx.lineTo(6, -20);
      ctx.fill();

      // Emergency Pulsing Aura
      if (isEm) {
        ctx.strokeStyle = '#f43f5e';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(0, 0, 16 + Math.sin(Date.now() / 100) * 4, 0, Math.PI * 2);
        ctx.stroke();
      }

      ctx.restore();
    });

  }, [vehicles, tlsState, currentPhase]);

  return (
    <div className="relative w-full h-[540px] flex items-center justify-center bg-[#070b16] rounded-2xl overflow-hidden border border-slate-800 shadow-2xl">
      <canvas ref={canvasRef} width={640} height={540} className="w-full h-full object-contain" />
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2 bg-slate-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/60 text-xs font-mono text-cyan-400">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
        2D VECTOR RADAR
      </div>
    </div>
  );
};
