'use client';

import { motion } from 'motion/react';
import { cn } from '@/lib/shadcn/utils';

export type DoctorState =
  'ready' | 'connecting' | 'listening' | 'speaking' | 'thinking' | 'ended' | 'idle';

export type DoctorTone = 'reassuring' | 'curious' | 'concerned';

export const DOCTOR_TONE_COLOR: Record<DoctorTone, string> = {
  reassuring: '#2dd4bf',
  curious: '#22d3ee',
  concerned: '#fbbf24',
};

interface DoctorAvatarProps {
  /** Which live state the doctor should express. */
  state?: DoctorState;
  /** Clinical empathy tone mirrored as glowing visual cues. */
  tone?: DoctorTone;
  className?: string;
}

const FILL = { transformBox: 'fill-box' as const, transformOrigin: 'center' as const };

/**
 * Cartoon doctor character — the friendly face of the voice agent.
 *
 * - listening: big curious eyes, gentle head tilt, orbiting audio sphere.
 * - speaking: open smiling mouth + radiating sound arcs.
 * - thinking: raised brows, thoughtful "?" bubble.
 * - ended: relaxed happy closed eyes.
 *
 * Empathy tone (reassuring / curious / concerned) shifts the brows, mouth,
 * the halo and the glow colour.
 */
export function DoctorAvatar({
  state = 'ready',
  tone = 'reassuring',
  className,
}: DoctorAvatarProps) {
  const listening = state === 'listening';
  const speaking = state === 'speaking';
  const thinking = state === 'thinking';
  const connecting = state === 'connecting';
  const ended = state === 'ended';
  const active = listening || speaking;
  const curious = tone === 'curious';
  const concerned = tone === 'concerned';
  const toneColor = DOCTOR_TONE_COLOR[tone];

  const Eye = ({ cx }: { cx: number }) => (
    <g>
      <ellipse cx={cx} cy="92" rx="9" ry="11" fill="#ffffff" />
      <circle cx={cx} cy="93" r={curious ? 4.6 : 4} fill="#2f2226">
        <animate attributeName="cy" values="93;90;93" dur="3.2s" repeatCount="indefinite" />
      </circle>
      <circle cx={cx + 2} cy="91" r="1.6" fill="#ffffff" />
    </g>
  );

  return (
    <motion.svg
      viewBox="0 0 200 200"
      className={cn('h-full w-full', className)}
      animate={{
        y: speaking ? [0, -3, 0] : [0, -4, 0],
        scale: active ? [1, 1.015, 1] : 1,
      }}
      transition={{
        y: speaking
          ? { duration: 0.8, repeat: Infinity, ease: 'easeInOut' }
          : { duration: 4.6, repeat: Infinity, ease: 'easeInOut' },
        scale: { duration: 2.6, repeat: Infinity, ease: 'easeInOut' },
      }}
      aria-label={`Health assistant doctor, ${state}`}
      role="img"
    >
      <defs>
        {/* Warm skin */}
        <radialGradient id="dh-skin" cx="0.45" cy="0.3" r="1">
          <stop offset="0" stopColor="#fbd3a8" />
          <stop offset="0.55" stopColor="#f0b887" />
          <stop offset="1" stopColor="#dfa06b" />
        </radialGradient>
        <linearGradient id="dh-skin-shadow" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e8ad7c" />
          <stop offset="1" stopColor="#c9884f" />
        </linearGradient>
        {/* White coat */}
        <linearGradient id="dh-coat" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#d4deec" />
        </linearGradient>
        <linearGradient id="dh-cap" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#c9d6e6" />
        </linearGradient>
        {/* Tone halo + glow */}
        <radialGradient id="dh-halo" cx="0.5" cy="0.42" r="0.75">
          <stop offset="0" stopColor={toneColor} stopOpacity="0.34" />
          <stop offset="0.7" stopColor={toneColor} stopOpacity="0.1" />
          <stop offset="1" stopColor={toneColor} stopOpacity="0" />
        </radialGradient>
        <filter id="dh-soft" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
        <filter id="dh-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="3.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Empathy tone halo */}
      <motion.circle
        cx="100"
        cy="95"
        r="88"
        fill="url(#dh-halo)"
        filter="url(#dh-soft)"
        animate={{ opacity: connecting ? [0.55, 1, 0.55] : [1, 0.75, 1] }}
        transition={{ duration: connecting ? 0.8 : 3, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Listening audio sphere — orbiting ring + satellites */}
      <motion.g
        animate={{ opacity: listening ? 1 : 0, scale: listening ? 1 : 0.85 }}
        transition={{ duration: 0.35 }}
        style={FILL}
      >
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: 14, repeat: Infinity, ease: 'linear' }}
          style={FILL}
        >
          <circle
            cx="100"
            cy="95"
            r="80"
            fill="none"
            stroke={toneColor}
            strokeWidth="1"
            strokeDasharray="2 9"
            strokeOpacity="0.5"
          />
          <circle cx="180" cy="95" r="2.6" fill={toneColor} filter="url(#dh-glow)" />
          <circle cx="100" cy="15" r="1.8" fill={toneColor} opacity="0.8" />
        </motion.g>
        <motion.g
          animate={{ rotate: -360 }}
          transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}
          style={FILL}
        >
          <circle
            cx="100"
            cy="95"
            r="66"
            fill="none"
            stroke={toneColor}
            strokeWidth="1"
            strokeDasharray="3 12"
            strokeOpacity="0.3"
          />
        </motion.g>
      </motion.g>

      {/* Ground shadow */}
      <motion.ellipse
        cx="100"
        cy="196"
        rx="42"
        ry="6"
        fill="#000000"
        opacity={active ? 0.18 : 0.12}
        filter="url(#dh-soft)"
        animate={{ rx: active ? [42, 46, 42] : 42, opacity: active ? [0.18, 0.1, 0.18] : 0.12 }}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Body — white coat */}
      <rect x="52" y="126" width="96" height="70" rx="28" fill="url(#dh-coat)" />
      <rect x="53.5" y="127.5" width="93" height="67" rx="26.5" fill="none" stroke="#aebfd4" strokeWidth="0.75" strokeOpacity="0.5" />
      {/* Lapels */}
      <path d="M100 130 L86 168 L100 178 Z" fill="#e3ebf5" />
      <path d="M100 130 L114 168 L100 178 Z" fill="#dce6f2" />
      {/* Coat buttons */}
      <circle cx="100" cy="174" r="2" fill="#8fa3bb" />
      {/* Stethoscope */}
      <path
        d="M88 124 C 78 142 86 154 100 154 C 114 154 122 142 112 124"
        fill="none"
        stroke="#3a4c63"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      <circle cx="88" cy="124" r="3" fill="#3a4c63" />
      <circle cx="112" cy="124" r="3" fill="#3a4c63" />
      <circle cx="100" cy="154" r="6" fill="#cdd7e4" stroke="#8fa3bb" strokeWidth="1.5" />
      <circle cx="100" cy="154" r="2" fill="#8fa3bb" />

      {/* Head group — tilts when listening / thinking / speaking */}
      <motion.g
        animate={{ rotate: listening ? -4 : thinking ? 3 : speaking ? -2 : 0 }}
        transition={{ duration: 0.7, ease: 'easeInOut' }}
        style={FILL}
      >
        {/* Neck */}
        <rect x="90" y="112" width="20" height="14" rx="6" fill="url(#dh-skin-shadow)" />
        {/* Ears */}
        <circle cx="57" cy="92" r="9" fill="url(#dh-skin)" />
        <circle cx="143" cy="92" r="9" fill="url(#dh-skin)" />

        {/* Head */}
        <circle cx="100" cy="92" r="44" fill="url(#dh-skin)" />
        {/* Hair / sideburns suggestion */}
        <path d="M58 84 C 56 64 66 54 76 52 C 70 60 68 72 70 84 Z" fill="#5b3a24" />
        <path d="M142 84 C 144 64 134 54 124 52 C 130 60 132 72 130 84 Z" fill="#5b3a24" />

        {/* Doctor's cap */}
        <path
          d="M58 84 C 56 52 74 42 100 42 C 126 42 144 52 142 84 C 126 74 74 74 58 84 Z"
          fill="url(#dh-cap)"
        />
        <path d="M62 78 C 78 68 122 68 138 78 C 124 71 76 71 62 78 Z" fill="#c3d2e4" opacity="0.7" />
        <rect x="60" y="78" width="80" height="7" rx="3.5" fill="#b8c9dd" />
        {/* Red cross badge */}
        <motion.rect
          x="95.5"
          y="56"
          width="9"
          height="18"
          rx="2"
          fill="#ef4444"
          filter="url(#dh-glow)"
          animate={{ opacity: connecting ? [0.6, 1, 0.6] : active ? [0.75, 1, 0.75] : 1 }}
          transition={{ duration: connecting ? 0.8 : 1.8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <rect x="91.5" y="60" width="17" height="9" rx="2" fill="#ef4444" filter="url(#dh-glow)" />

        {/* Brows */}
        {ended ? null : concerned ? (
          <g>
            <path d="M70 80 Q82 85 92 80" stroke="#7a5b3d" strokeWidth="3" strokeLinecap="round" fill="none" />
            <path d="M108 80 Q118 85 130 80" stroke="#7a5b3d" strokeWidth="3" strokeLinecap="round" fill="none" />
          </g>
        ) : curious ? (
          <g>
            <path d="M70 77 Q82 72 92 77" stroke="#7a5b3d" strokeWidth="3" strokeLinecap="round" fill="none" />
            <path d="M108 77 Q118 72 130 77" stroke="#7a5b3d" strokeWidth="3" strokeLinecap="round" fill="none" />
          </g>
        ) : (
          <g>
            <path d="M70 81 Q82 77 92 81" stroke="#7a5b3d" strokeWidth="3" strokeLinecap="round" fill="none" />
            <path d="M108 81 Q118 77 130 81" stroke="#7a5b3d" strokeWidth="3" strokeLinecap="round" fill="none" />
          </g>
        )}

        {/* Eyes — blink */}
        <motion.g
          animate={{ scaleY: thinking ? 0 : [1, 1, 0.08, 1, 1] }}
          transition={{ duration: 4.6, repeat: Infinity, times: [0, 0.9, 0.94, 0.98, 1] }}
          style={FILL}
        >
          {ended ? (
            <g>
              <path d="M72 92 C76 86 82 86 86 92" stroke="#3a2a22" strokeWidth="3" strokeLinecap="round" fill="none" />
              <path d="M114 92 C118 86 124 86 128 92" stroke="#3a2a22" strokeWidth="3" strokeLinecap="round" fill="none" />
            </g>
          ) : (
            <motion.g
              animate={{ scale: listening ? 1.12 : curious ? 1.06 : 1 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              style={FILL}
            >
              <Eye cx={83} />
              <Eye cx={117} />
            </motion.g>
          )}
        </motion.g>

        {/* Rosy cheeks */}
        <circle cx="71" cy="102" r="6" fill="#ff9e9e" opacity="0.45" />
        <circle cx="129" cy="102" r="6" fill="#ff9e9e" opacity="0.45" />

        {/* Nose */}
        <circle cx="100" cy="104" r="3" fill="#d99c6b" />

        {/* Mouth */}
        {speaking ? (
          <g>
            <motion.g
              animate={{ scaleY: [0.55, 1, 0.55] }}
              transition={{ duration: 0.45, repeat: Infinity, ease: 'easeInOut' }}
              style={FILL}
              initial={false}
            >
              <path d="M88 109 C 92 105 108 105 112 109 C 108 123 92 123 88 109 Z" fill="#8a3b2e" />
              <ellipse cx="100" cy="114" rx="7" ry="3.5" fill="#f0a5a5" />
            </motion.g>
            {/* Sound arcs */}
            <motion.path
              d="M118 104 A12 12 0 0 1 118 122"
              stroke={toneColor}
              strokeWidth="2.5"
              strokeLinecap="round"
              fill="none"
              style={FILL}
              animate={{ opacity: [0.2, 0.8, 0.2], scale: [0.85, 1.15, 0.85] }}
              transition={{ duration: 0.8, repeat: Infinity, ease: 'easeInOut' }}
            />
            <motion.path
              d="M125 99 A18 18 0 0 1 125 127"
              stroke={toneColor}
              strokeWidth="2.5"
              strokeLinecap="round"
              fill="none"
              style={FILL}
              animate={{ opacity: [0.15, 0.6, 0.15], scale: [0.85, 1.15, 0.85] }}
              transition={{ duration: 0.8, repeat: Infinity, delay: 0.12, ease: 'easeInOut' }}
            />
          </g>
        ) : thinking ? (
          <circle cx="100" cy="111" r="3.5" fill="none" stroke="#8a5a34" strokeWidth="2.5" />
        ) : concerned ? (
          <path d="M88 113 Q94 109 100 113 Q106 117 112 113" stroke="#8a5a34" strokeWidth="3" strokeLinecap="round" fill="none" />
        ) : (
          <motion.path
            d="M88 109 Q100 118 112 109"
            stroke="#7a3b2e"
            strokeWidth="3.5"
            strokeLinecap="round"
            fill="none"
            animate={{ opacity: active ? [0.75, 1, 0.75] : 1 }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
        )}
      </motion.g>

      {/* Thinking — thought bubble */}
      <motion.g animate={{ opacity: thinking ? 1 : 0 }} transition={{ duration: 0.2 }}>
        <circle cx="152" cy="36" r="3.5" fill="#ffffff" stroke={toneColor} strokeOpacity="0.8" />
        <circle cx="162" cy="26" r="5" fill="#ffffff" stroke={toneColor} strokeOpacity="0.8" />
        <motion.ellipse
          cx="172"
          cy="12"
          rx="11"
          ry="9"
          fill="#ffffff"
          stroke={toneColor}
          strokeOpacity="0.9"
          filter="url(#dh-glow)"
          animate={{ y: [0, -2, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
        >
          <animate attributeName="opacity" values="0.85;1;0.85" dur="1.6s" repeatCount="indefinite" />
        </motion.ellipse>
        <text
          x="172"
          y="16"
          textAnchor="middle"
          fontSize="13"
          fontWeight="800"
          fill={toneColor}
          style={{ fontFamily: 'var(--font-commit-mono), monospace' }}
        >
          ?
        </text>
      </motion.g>
    </motion.svg>
  );
}
