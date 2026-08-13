'use client';

import { useEffect, useRef } from 'react';
import { useTheme } from 'next-themes';
import { useAgent } from '@livekit/components-react';

interface MeshParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  z: number; // 0..1 pseudo-depth
  r: number;
  phase: number;
  wave: number;
}

const LINK_DIST = 165;

/**
 * Interactive 3D-feel gravity-mesh. Glowing nodes drift toward the centre with
 * a pseudo-depth channel (size/alpha/brightness scale with z) and a slow
 * differential rotation, so the network reads as a rotating 3D volume instead
 * of a flat grid. When the agent listens or speaks, the whole field brightens,
 * waves ripple through it and the centre pulses.
 */
export function MeshBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = useTheme();
  const { state } = useAgent();
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let raf = 0;
    const particles: MeshParticle[] = [];
    const dark = resolvedTheme !== 'light';
    const rgb = dark ? '45, 212, 191' : '107, 142, 113';
    const glowRgb = dark ? '34, 211, 238' : '107, 142, 113';
    const depthGap = 0.00016;

    const initParticles = () => {
      particles.length = 0;
      const count = Math.min(110, Math.max(60, Math.round((width * height) / 15000)));
      for (let i = 0; i < count; i++) {
        const z = Math.pow(Math.random(), 1.6); // bias toward far field
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          z,
          r: 0.8 + Math.random() * 2,
          phase: Math.random() * Math.PI * 2,
          wave: Math.random() * Math.PI * 2,
        });
      }
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.offsetWidth;
      height = canvas.offsetHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      initParticles();
    };

    const draw = (t: number) => {
      ctx.clearRect(0, 0, width, height);

      const s = stateRef.current;
      const active = s === 'speaking' || s === 'listening';
      const intensity = active ? 1 : 0.55;
      const cx = width / 2;
      const cy = height / 2;

      // Deep-space vignette + centre bloom.
      const vignette = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(width, height) * 0.75);
      vignette.addColorStop(0, dark ? 'rgba(11,15,25,0)' : 'rgba(251,246,236,0)');
      vignette.addColorStop(0.55, dark ? 'rgba(8,12,22,0)' : 'rgba(251,246,236,0)');
      vignette.addColorStop(1, dark ? 'rgba(4,6,12,0.75)' : 'rgba(230,220,200,0.5)');
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, width, height);

      const bloom = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(width, height) * 0.5);
      bloom.addColorStop(0, `rgba(${rgb}, ${(0.05 + intensity * 0.05).toFixed(3)})`);
      bloom.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = bloom;
      ctx.fillRect(0, 0, width, height);

      // Simulate 3D: rotate each particle around centre at a rate that grows
      // with distance — gives the network a slow volumetric spin.
      const angleInc = depthGap * (0.6 + intensity * 0.8);
      for (const p of particles) {
        const dx = p.x - cx;
        const dy = p.y - cy;
        const dist = Math.hypot(dx, dy) || 1;
        const spin = angleInc * (0.35 + dist / 900);
        const cos = Math.cos(spin);
        const sin = Math.sin(spin);
        const nx = cx + dx * cos - dy * sin;
        const ny = cy + dx * sin + dy * cos;
        p.vx += (nx - p.x) * 0.05;
        p.vy += (ny - p.y) * 0.05;

        // Soft gravity toward centre + breathing z.
        const pull = 0.000045 * Math.min(1, dist / 460);
        p.vx += (dx / dist) * pull;
        p.vy += (dy / dist) * pull;
        p.vx *= 0.996;
        p.vy *= 0.996;
        p.x += p.vx;
        p.y += p.vy;
        p.z = Math.max(0.08, Math.min(1, p.z + Math.sin(t * 0.00022 + p.wave) * 0.0009));

        if (active) {
          const sway = Math.sin(t * 0.0016 + p.wave) * 1.1;
          p.x += Math.sin(p.wave * 2 + t * 0.001) * 0.22 * sway;
          p.y += Math.cos(p.wave * 2 + t * 0.001) * 0.22 * sway;
        }

        if (p.x < -24) p.x = width + 24;
        if (p.x > width + 24) p.x = -24;
        if (p.y < -24) p.y = height + 24;
        if (p.y > height + 24) p.y = -24;
      }

      // Links (line width + alpha scale with depth for parallax).
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const ldx = a.x - b.x;
          const ldy = a.y - b.y;
          const d2 = ldx * ldx + ldy * ldy;
          if (d2 < LINK_DIST * LINK_DIST) {
            const d = Math.sqrt(d2);
            const depth = 0.45 + 0.55 * ((a.z + b.z) / 2);
            const breathe = 0.62 + 0.38 * Math.sin(t * 0.002 + a.phase);
            const alpha = (1 - d / LINK_DIST) * 0.38 * intensity * depth * breathe;
            if (alpha > 0.012) {
              ctx.strokeStyle = `rgba(${rgb}, ${alpha.toFixed(3)})`;
              ctx.lineWidth = active ? 1.1 * depth : 0.7 * depth;
              ctx.beginPath();
              ctx.moveTo(a.x, a.y);
              ctx.lineTo(b.x, b.y);
              ctx.stroke();
            }
          }
        }
      }

      // Glowing nodes — closer (higher z) = bigger, brighter.
      for (const p of particles) {
        const glow = active ? 0.55 + 0.45 * Math.sin(t * 0.006 + p.phase) : 0.4;
        const r = p.r * (0.7 + 0.8 * p.z) * (active ? 1.45 : 1);
        const a = (0.35 + 0.65 * p.z) * (0.35 + 0.65 * glow) * intensity;
        ctx.shadowBlur = active ? 6 + 8 * p.z : 3 + 5 * p.z;
        ctx.shadowColor = `rgba(${glowRgb}, 0.85)`;
        ctx.fillStyle = `rgba(${rgb}, ${Math.min(1, a).toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;

      raf = requestAnimationFrame(draw);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [resolvedTheme]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 h-svh w-full"
    />
  );
}
