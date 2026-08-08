'use client';

import { useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';
import { cn } from '@/lib/shadcn/utils';

interface TiltCardProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * A small 3D tilt surface — the card rotates gently toward the cursor and
 * carries a moving glare highlight, like a glossy storybook charm.
 */
export function TiltCard({ children, className }: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const mx = useMotionValue(0.5);
  const my = useMotionValue(0.5);

  const rotateX = useSpring(useTransform(my, [0, 1], [8, -8]), { stiffness: 260, damping: 22 });
  const rotateY = useSpring(useTransform(mx, [0, 1], [-8, 8]), { stiffness: 260, damping: 22 });
  const glare = useTransform(
    [mx, my],
    ([x, y]) =>
      `radial-gradient(circle at ${(x as number) * 100}% ${(y as number) * 100}%, rgba(255,255,255,0.4), transparent 55%)`
  );

  return (
    <motion.div
      ref={ref}
      style={{ rotateX, rotateY, transformPerspective: 900 }}
      onMouseMove={(e) => {
        const rect = ref.current?.getBoundingClientRect();
        if (!rect) return;
        mx.set((e.clientX - rect.left) / rect.width);
        my.set((e.clientY - rect.top) / rect.height);
      }}
      onMouseLeave={() => {
        mx.set(0.5);
        my.set(0.5);
      }}
      className={cn('relative [transform-style:preserve-3d]', className)}
    >
      {children}
      <motion.span
        aria-hidden
        style={{ background: glare }}
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-60 dark:opacity-30"
      />
    </motion.div>
  );
}
