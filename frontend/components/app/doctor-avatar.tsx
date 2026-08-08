'use client';

import { motion } from 'motion/react';
import { cn } from '@/lib/shadcn/utils';

export type DoctorState =
  'ready' | 'connecting' | 'listening' | 'speaking' | 'ended' | 'idle' | 'thinking';

interface DoctorAvatarProps {
  /** Which live state the doctor should express. */
  state?: DoctorState;
  className?: string;
}

const WAVE_SFX = { transformBox: 'fill-box' as const, transformOrigin: 'center' as const };

/**
 * The single, persistent agent character — a friendly Indian doctor. The same
 * face stays on screen through every state (ready / connecting / listening /
 * speaking / ended) so the agent always feels like a living companion.
 */
export function DoctorAvatar({ state = 'ready', className }: DoctorAvatarProps) {
  const listening = state === 'listening';
  const speaking = state === 'speaking';
  const happy = state === 'ended';

  return (
    <motion.svg
      viewBox="0 0 200 200"
      className={cn('h-full w-full', className)}
      animate={speaking ? { y: [0, -3, 0] } : { y: 0 }}
      transition={
        speaking ? { duration: 0.8, repeat: Infinity, ease: 'easeInOut' } : { duration: 0.3 }
      }
      aria-hidden
    >
      <defs>
        <radialGradient id="ss-skin" cx="0.38" cy="0.32" r="0.95">
          <stop offset="0" stopColor="#eab290" />
          <stop offset="1" stopColor="#cd8a68" />
        </radialGradient>
        <linearGradient id="ss-coat" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#e9e3d2" />
        </linearGradient>
      </defs>

      {/* White coat */}
      <path d="M38 200 C44 166 70 154 100 154 C130 154 156 166 162 200 Z" fill="url(#ss-coat)" />
      <path d="M100 154 C93 170 95 186 100 200" stroke="#dcd6c3" strokeWidth="3" fill="none" />

      {/* Scrub collar */}
      <path d="M76 160 C88 178 112 178 124 160 C116 172 84 172 76 160 Z" fill="#6b8e71" />

      {/* Stethoscope */}
      <path
        d="M68 128 C56 158 66 180 100 188 C134 180 144 158 132 128"
        stroke="#5b6b7a"
        strokeWidth="5"
        fill="none"
        strokeLinecap="round"
      />
      <circle cx="100" cy="192" r="9" fill="#fffdf6" stroke="#d9a441" strokeWidth="4" />

      {/* Neck */}
      <rect x="88" y="128" width="24" height="30" rx="10" fill="#cd8a68" />

      {/* Ears */}
      <ellipse cx="50" cy="116" rx="9" ry="13" fill="#cd8a68" />
      <ellipse cx="150" cy="116" rx="9" ry="13" fill="#cd8a68" />

      {/* Listening waves — left ear */}
      <motion.path
        d="M32 100 A12 12 0 0 1 32 128"
        stroke="#6b8e71"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        style={WAVE_SFX}
        animate={{ opacity: listening ? [0, 0.9, 0] : 0, scale: listening ? [0.8, 1.12, 0.8] : 1 }}
        transition={{ duration: 1.6, repeat: Infinity, delay: 0, ease: 'easeInOut' }}
      />
      <motion.path
        d="M29 92 A18 18 0 0 1 29 136"
        stroke="#6b8e71"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        style={WAVE_SFX}
        animate={{ opacity: listening ? [0, 0.9, 0] : 0, scale: listening ? [0.8, 1.12, 0.8] : 1 }}
        transition={{ duration: 1.6, repeat: Infinity, delay: 0.35, ease: 'easeInOut' }}
      />
      <motion.path
        d="M26 84 A24 24 0 0 1 26 144"
        stroke="#6b8e71"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        style={WAVE_SFX}
        animate={{ opacity: listening ? [0, 0.9, 0] : 0, scale: listening ? [0.8, 1.12, 0.8] : 1 }}
        transition={{ duration: 1.6, repeat: Infinity, delay: 0.7, ease: 'easeInOut' }}
      />

      {/* Hair */}
      <path
        d="M46 98 C46 60 66 42 100 42 C134 42 154 60 154 98 C152 76 138 58 100 58 C62 58 48 76 46 98 Z"
        fill="#3a2a24"
      />
      <path d="M60 64 C70 50 90 44 112 48 C100 58 86 62 72 70 Z" fill="#4a372f" />

      {/* Head */}
      <circle cx="100" cy="100" r="54" fill="url(#ss-skin)" />

      {/* Brows */}
      <path
        d="M74 90 C80 85 92 85 97 89"
        stroke="#3a2a24"
        strokeWidth="3.5"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M103 89 C108 85 120 85 126 90"
        stroke="#3a2a24"
        strokeWidth="3.5"
        fill="none"
        strokeLinecap="round"
      />

      {/* Eyes (blink) */}
      <motion.g
        style={WAVE_SFX}
        animate={{ scaleY: [1, 1, 0.08, 1, 1] }}
        transition={{ duration: 4.6, repeat: Infinity, times: [0, 0.9, 0.94, 0.98, 1] }}
      >
        <ellipse cx="84" cy="100" rx="7" ry="9" fill="#fffdf8" />
        <ellipse cx="116" cy="100" rx="7" ry="9" fill="#fffdf8" />
        <circle cx="84" cy="102" r="3.4" fill="#3a2a24" />
        <circle cx="116" cy="102" r="3.4" fill="#3a2a24" />
      </motion.g>

      {/* Listening focus — pupils turn inward */}
      <motion.g
        style={WAVE_SFX}
        animate={{ opacity: listening ? 1 : 0 }}
        transition={{ duration: 0.3 }}
      >
        <circle cx="86.5" cy="102" r="3.2" fill="#3a2a24" />
        <circle cx="113.5" cy="102" r="3.2" fill="#3a2a24" />
        <circle cx="87.5" cy="100.5" r="1.3" fill="#ffffff" />
        <circle cx="112.5" cy="100.5" r="1.3" fill="#ffffff" />
      </motion.g>

      {/* Nose */}
      <path
        d="M100 104 C97 111 96 114 100 117"
        stroke="#b06f52"
        strokeWidth="2.6"
        fill="none"
        strokeLinecap="round"
      />

      {/* Smile (ready / connecting / ended) */}
      <motion.path
        d={happy ? 'M84 120 C92 130 108 130 116 120' : 'M86 121 C93 130 107 130 114 121'}
        stroke="#8a4a33"
        strokeWidth="3.6"
        strokeLinecap="round"
        fill="none"
        style={WAVE_SFX}
        animate={{ opacity: speaking ? 0 : 1, scale: [1, 1.04, 1] }}
        transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Speaking mouth + sound waves */}
      <motion.g
        style={WAVE_SFX}
        animate={{ opacity: speaking ? 1 : 0 }}
        transition={{ duration: 0.2 }}
      >
        <ellipse cx="100" cy="126" rx="8.5" ry="7" fill="#7c2d20" />
        <ellipse cx="100" cy="129" rx="5.5" ry="3" fill="#e08a76" />
        <motion.path
          d="M118 116 A12 12 0 0 1 118 134"
          stroke="#d9a441"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          style={WAVE_SFX}
          animate={{ opacity: [0.3, 0.9, 0.3], scale: [0.85, 1.14, 0.85] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: 0, ease: 'easeInOut' }}
        />
        <motion.path
          d="M126 108 A18 18 0 0 1 126 142"
          stroke="#d9a441"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          style={WAVE_SFX}
          animate={{ opacity: [0.3, 0.9, 0.3], scale: [0.85, 1.14, 0.85] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: 0.18, ease: 'easeInOut' }}
        />
        <motion.path
          d="M134 100 A24 24 0 0 1 134 150"
          stroke="#d9a441"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          style={WAVE_SFX}
          animate={{ opacity: [0.3, 0.9, 0.3], scale: [0.85, 1.14, 0.85] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: 0.36, ease: 'easeInOut' }}
        />
      </motion.g>
    </motion.svg>
  );
}
