'use client';

import { useMemo } from 'react';
import { motion } from 'motion/react';
import { cn } from '@/lib/shadcn/utils';

/**
 * Layered aurora glows that drift lazily behind the scene — the magical,
 * dreamy depth that makes the garden feel alive.
 */
export function AuroraGlow({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn('pointer-events-none absolute inset-0', className)}>
      <motion.div
        animate={{ x: [0, 70, 0], y: [0, -50, 0] }}
        transition={{ duration: 24, repeat: Infinity, ease: 'easeInOut' }}
        className="bg-sage/18 absolute -top-32 -left-24 size-[30rem] rounded-full blur-3xl"
      />
      <motion.div
        animate={{ x: [0, -60, 0], y: [0, 60, 0] }}
        transition={{ duration: 28, repeat: Infinity, ease: 'easeInOut' }}
        className="bg-gold/15 absolute top-1/4 -right-40 size-[30rem] rounded-full blur-3xl"
      />
      <motion.div
        animate={{ x: [0, 50, 0], y: [0, -40, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: 'easeInOut' }}
        className="bg-peach/16 absolute -bottom-40 left-1/4 size-[30rem] rounded-full blur-3xl"
      />
      <motion.div
        animate={{ x: [0, -40, 0], y: [0, 40, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut' }}
        className="bg-sage-light/18 absolute top-0 right-1/4 size-72 rounded-full blur-3xl"
      />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,transparent_35%,var(--background))]" />
    </div>
  );
}

/**
 * Tiny four-pointed stars that twinkle across the scene like a storybook sky.
 */
export function TwinklingStars({ count = 16 }: { count?: number }) {
  const stars = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        top: `${(i * 41) % 100}%`,
        left: `${(i * 67 + 7) % 100}%`,
        delay: (i * 0.7) % 4,
        size: 6 + (i % 3) * 3,
      })),
    [count]
  );

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {stars.map((star, i) => (
        <motion.svg
          key={i}
          viewBox="0 0 24 24"
          className="absolute"
          style={{ top: star.top, left: star.left, width: star.size, height: star.size }}
          animate={{ opacity: [0, 1, 0], scale: [0.6, 1.2, 0.6] }}
          transition={{ duration: 3.4, repeat: Infinity, delay: star.delay, ease: 'easeInOut' }}
        >
          <path
            d="M12 1 L13.8 8.2 L21 10 L13.8 11.8 L12 19 L10.2 11.8 L3 10 L10.2 8.2 Z"
            fill="#d9a441"
          />
        </motion.svg>
      ))}
    </div>
  );
}

/**
 * Soft, hand-drawn botanical illustrations (tulsi sprig, lotus, scattered
 * leaves) pinned to the corners of a view — the Indian storybook identity.
 */
export function BotanicalLeaves({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn('pointer-events-none absolute inset-0', className)}>
      {/* Tulsi sprig — top right */}
      <svg
        viewBox="0 0 200 200"
        className="text-forest/10 dark:text-cream/10 absolute -top-10 -right-12 size-64 rotate-12 md:size-80"
        fill="none"
      >
        <defs>
          <path id="tulsi-leaf" d="M0 0 C12 -16, 36 -16, 48 0 C36 16, 12 16, 0 0 Z" />
        </defs>
        <path
          d="M160 20 C140 60 112 92 66 138"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <use
          href="#tulsi-leaf"
          transform="translate(122,40) rotate(-35) scale(0.55)"
          fill="currentColor"
        />
        <use
          href="#tulsi-leaf"
          transform="translate(106,60) rotate(38) scale(0.55)"
          fill="currentColor"
        />
        <use
          href="#tulsi-leaf"
          transform="translate(92,82) rotate(-35) scale(0.68)"
          fill="currentColor"
        />
        <use
          href="#tulsi-leaf"
          transform="translate(78,106) rotate(38) scale(0.68)"
          fill="currentColor"
        />
        <use
          href="#tulsi-leaf"
          transform="translate(64,128) rotate(-35) scale(0.8)"
          fill="currentColor"
        />
      </svg>

      {/* Lotus — bottom left */}
      <svg
        viewBox="0 0 160 160"
        className="text-gold/15 dark:text-gold/15 absolute -bottom-14 -left-14 size-64 md:size-80"
        fill="none"
      >
        <g transform="translate(80,150)">
          <g transform="rotate(-55) scale(0.8)">
            <path
              d="M0 0 C-12 -30 -12 -70 0 -84 C12 -70 12 -30 0 0 Z"
              fill="currentColor"
              opacity="0.5"
            />
          </g>
          <g transform="rotate(55) scale(0.8)">
            <path
              d="M0 0 C-12 -30 -12 -70 0 -84 C12 -70 12 -30 0 0 Z"
              fill="currentColor"
              opacity="0.5"
            />
          </g>
          <g transform="rotate(-30)">
            <path
              d="M0 0 C-12 -30 -12 -70 0 -84 C12 -70 12 -30 0 0 Z"
              fill="currentColor"
              opacity="0.72"
            />
          </g>
          <g transform="rotate(30)">
            <path
              d="M0 0 C-12 -30 -12 -70 0 -84 C12 -70 12 -30 0 0 Z"
              fill="currentColor"
              opacity="0.72"
            />
          </g>
          <path d="M0 0 C-12 -30 -12 -70 0 -84 C12 -70 12 -30 0 0 Z" fill="currentColor" />
        </g>
      </svg>

      {/* Small plant — bottom right */}
      <svg
        viewBox="0 0 200 200"
        className="text-sage/15 dark:text-sage-light/15 absolute -right-8 -bottom-12 size-56 md:size-72"
        fill="none"
      >
        <path
          d="M160 180 C152 130 138 96 112 60"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path d="M150 120 C138 114 128 104 122 90 C136 94 146 104 150 120 Z" fill="currentColor" />
        <path
          d="M140 150 C126 146 116 138 110 126 C126 130 136 138 140 150 Z"
          fill="currentColor"
        />
        <path d="M112 60 C112 40 122 30 138 26 C132 44 122 54 112 60 Z" fill="currentColor" />
        <path
          d="M176 100 C168 92 162 82 160 70 C172 76 178 86 180 98 C178 98 177 99 176 100 Z"
          fill="currentColor"
        />
      </svg>
    </div>
  );
}

/**
 * Tiny glowing fireflies that drift upward through the garden at different
 * depths — each one a soft golden, sage or peach mote.
 */
export function FloatingParticles({ count = 14 }: { count?: number }) {
  const particles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        left: `${(i * 83 + 5) % 100}%`,
        delay: (i * 1.37) % 6,
        duration: 8 + (i % 5) * 2.4,
        size: 3 + (i % 3) * 2,
        color: i % 3 === 0 ? '#d9a441' : i % 3 === 1 ? '#6b8e71' : '#e9a58f',
        blur: i % 2 === 0 ? 'blur-[2px]' : 'blur-[1px]',
      })),
    [count]
  );

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {particles.map((p, i) => (
        <motion.span
          key={i}
          initial={{ y: '112%', opacity: 0 }}
          animate={{ y: '-112%', opacity: [0, 0.7, 0] }}
          transition={{ duration: p.duration, delay: p.delay, repeat: Infinity, ease: 'linear' }}
          className={cn('absolute bottom-0 rounded-full', p.blur)}
          style={{ left: p.left, width: p.size, height: p.size, background: p.color }}
        />
      ))}
    </div>
  );
}
