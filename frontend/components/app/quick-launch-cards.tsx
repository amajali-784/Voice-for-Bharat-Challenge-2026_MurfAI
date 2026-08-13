'use client';

import { ArrowUpRight, History, MapPin } from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/lib/shadcn/utils';

export type QuickLaunchId = 'clinic' | 'history';

const QUICK_LAUNCH = [
  {
    id: 'clinic',
    icon: MapPin,
    en: 'Find Nearby Clinic',
    hi: 'नज़दीकी क्लिनिक खोजें',
    hint: 'नज़दीकी अस्पताल / क्लिनिक पता करें',
    accent: 'from-teal-400/90 to-cyan-500/80',
  },
  {
    id: 'history',
    icon: History,
    en: 'Check Symptom History',
    hi: 'लक्षण इतिहास देखें',
    hint: 'पिछली बातचीत का सारांश',
    accent: 'from-sky-400/90 to-indigo-500/80',
  },
] as const;

interface QuickLaunchCardsProps {
  onSelect: (id: QuickLaunchId) => void;
  /** Compact horizontal pills for use inside the live session. */
  compact?: boolean;
  className?: string;
}

export function QuickLaunchCards({ onSelect, compact = false, className }: QuickLaunchCardsProps) {
  if (compact) {
    return (
      <div className={cn('flex flex-wrap items-center justify-center gap-2', className)}>
        {QUICK_LAUNCH.map(({ id, icon: Icon, en, hi, accent }) => (
          <motion.button
            key={id}
            type="button"
            onClick={() => onSelect(id)}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.96 }}
            className="glass-chip group flex items-center gap-2 rounded-full py-1.5 pr-3.5 pl-1.5 transition-shadow hover:shadow-[0_0_20px_rgba(45,212,191,0.3)]"
          >
            <span
              className={`flex size-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-b ${accent} text-[#06201a]`}
            >
              <Icon className="size-3.5" />
            </span>
            <span className="text-xs font-bold whitespace-nowrap">{en}</span>
            <span
              className="text-muted-foreground text-[10px] font-medium whitespace-nowrap"
              style={{ fontFamily: 'var(--font-mukta)' }}
            >
              {hi}
            </span>
          </motion.button>
        ))}
      </div>
    );
  }

  return (
    <div
      className={cn('grid w-full max-w-xl grid-cols-1 gap-3 min-[560px]:grid-cols-2', className)}
    >
      {QUICK_LAUNCH.map(({ id, icon: Icon, en, hi, accent }) => (
        <motion.button
          key={id}
          type="button"
          onClick={() => onSelect(id)}
          whileHover={{ y: -3 }}
          whileTap={{ y: 0, scale: 0.98 }}
          className="glass-panel group flex cursor-pointer items-center gap-3 rounded-2xl border px-4 py-4 text-left transition-all duration-300 hover:border-teal-400/50 hover:shadow-[0_12px_40px_-10px_rgba(45,212,191,0.35)] focus-visible:ring-2 focus-visible:ring-teal-400/60"
        >
          <span
            className={`flex size-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-b ${accent} text-[#06201a] shadow-lg transition-transform duration-300 group-hover:scale-105`}
          >
            <Icon className="size-5" />
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="flex items-center gap-1.5 text-sm leading-tight font-bold">
              {en}
              <ArrowUpRight className="text-muted-foreground size-3.5 shrink-0 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </span>
            <span
              className="text-muted-foreground mt-1 text-xs leading-snug font-medium"
              style={{ fontFamily: 'var(--font-mukta)' }}
            >
              {hi}
            </span>
          </span>
        </motion.button>
      ))}
    </div>
  );
}
