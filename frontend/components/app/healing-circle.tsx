'use client';

import { motion } from 'motion/react';
import { DoctorAvatar, type DoctorState } from '@/components/app/doctor-avatar';
import { cn } from '@/lib/shadcn/utils';

export type HealingState = 'ready' | 'connecting' | 'listening' | 'speaking' | 'ended';

interface HealingCircleProps {
  /** Which agent state the magic ring should reflect. */
  state: HealingState;
  /** Diameter of the circle. Accepts any CSS length. */
  size?: string | number;
  /** Live audio energy (0..1) to drive the pulse while listening/speaking. */
  energy?: number;
  className?: string;
  /** Optional center content — defaults to the resident DoctorAvatar. */
  children?: React.ReactNode;
}

const SPARKLES = [
  { top: '4%', left: '52%', delay: 0 },
  { top: '14%', left: '20%', delay: 0.6 },
  { top: '10%', left: '82%', delay: 1.2 },
  { top: '30%', left: '4%', delay: 1.8 },
  { top: '32%', left: '94%', delay: 0.9 },
  { top: '55%', left: '10%', delay: 2.3 },
  { top: '58%', left: '88%', delay: 1.5 },
  { top: '82%', left: '26%', delay: 2.8 },
  { top: '78%', left: '74%', delay: 0.3 },
  { top: '96%', left: '50%', delay: 2.1 },
];

export function HealingCircle({
  state,
  size = 'clamp(220px, 54vw, 320px)',
  energy = 0,
  className,
  children,
}: HealingCircleProps) {
  const isConnecting = state === 'connecting';
  const isEnded = state === 'ended';
  const pulse = Math.min(1, Math.max(0.5, energy));

  const ringMask = 'radial-gradient(closest-side, transparent 79%, black 81%)';

  return (
    <div
      className={cn('relative select-none', className)}
      style={{ width: size, height: size }}
      aria-hidden
    >
      {/* Ground shadow — grounds the floating doctor for a 3D pop */}
      <motion.div
        animate={{ scale: isEnded ? 0.8 : isConnecting ? 1.15 : 1, opacity: isEnded ? 0.25 : 0.45 }}
        transition={{ duration: 1.2, ease: 'easeInOut' }}
        className="bg-forest/30 absolute -bottom-[9%] left-1/2 h-[9%] w-[58%] -translate-x-1/2 rounded-[50%] blur-xl dark:bg-black/50"
      />

      {/* Deep sage halo */}
      <div
        className="absolute -inset-[16%] rounded-full blur-3xl"
        style={{
          background:
            'radial-gradient(circle at center, color-mix(in srgb, #6b8e71 26%, transparent), transparent 68%)',
        }}
      />

      {/* Rotating conic "magic" ring */}
      <div
        className="absolute -inset-[3%] rounded-full"
        style={{ maskImage: ringMask, WebkitMaskImage: ringMask }}
      >
        <motion.div
          className="absolute inset-[-30%]"
          style={{
            background:
              'conic-gradient(from 0deg, transparent 0%, rgba(217,164,65,0.9) 7%, transparent 14%, transparent 42%, rgba(107,142,113,0.85) 50%, transparent 58%, transparent 80%, rgba(233,165,143,0.8) 88%, transparent 96%)',
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}
        />
      </div>
      {/* Counter-glow ring for depth */}
      <div className="border-sage/20 dark:border-sage-light/15 absolute -inset-[3%] rounded-full border" />

      {/* Rotating dashed outer ring */}
      <motion.div
        animate={{ rotate: isConnecting ? 360 : 0 }}
        transition={
          isConnecting
            ? { duration: 4.5, repeat: Infinity, ease: 'linear' }
            : { duration: 120, repeat: Infinity, ease: 'linear' }
        }
        className="border-sage/40 dark:border-sage-light/25 absolute inset-0 rounded-full border border-dashed"
      />

      {/* Dots travelling the ring (counter-rotate) */}
      <motion.div
        animate={{ rotate: isConnecting ? -360 : 0 }}
        transition={{
          duration: isConnecting ? 9 : 70,
          repeat: Infinity,
          ease: 'linear',
        }}
        className="absolute inset-0"
      >
        <span className="bg-gold/80 absolute top-0 left-1/2 size-2 -translate-x-1/2 rounded-full" />
        <span className="bg-sage/70 absolute top-1/2 right-0 size-1.5 -translate-y-1/2 rounded-full" />
        <span className="bg-peach/80 absolute bottom-[14%] left-[7%] size-1.5 rounded-full" />
      </motion.div>

      {/* Pulsing glow rings */}
      <motion.span
        animate={{
          scale: state === 'ready' ? [1, 1.07, 1] : isEnded ? 0.96 : [1, pulse + 0.12, 1],
          opacity: state === 'ready' ? [0.6, 0.95, 0.6] : isEnded ? 0.2 : [0.55, 0.9, 0.55],
        }}
        transition={{
          duration: state === 'ready' ? 4 : 1.5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        className="border-sage/50 dark:border-sage-light/40 absolute inset-5 rounded-full border"
      />
      <motion.span
        animate={{
          scale: [1, pulse + 0.22, 1],
          opacity: isEnded ? 0.1 : [0.3, 0.55, 0.3],
        }}
        transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut', delay: 0.6 }}
        className="border-gold/40 dark:border-gold/30 absolute inset-12 rounded-full border"
      />

      {/* Sparkles */}
      {SPARKLES.map((sparkle, i) => (
        <motion.span
          key={i}
          animate={{ opacity: [0.15, 0.9, 0.15], scale: [0.7, 1.25, 0.7] }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: sparkle.delay,
          }}
          className="bg-gold absolute size-1.5 rounded-full"
          style={{ top: sparkle.top, left: sparkle.left }}
        />
      ))}

      {/* The resident doctor, floating gently in the middle */}
      <motion.div
        animate={{ y: [0, -9, 0] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute inset-[20%] flex items-center justify-center"
      >
        <motion.div
          animate={{ scale: isEnded ? [1, 1.02, 1] : [1, pulse, 1] }}
          transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
          className="h-full w-full"
        >
          {children ?? <DoctorAvatar state={state as DoctorState} tone="reassuring" />}
        </motion.div>
      </motion.div>
    </div>
  );
}
