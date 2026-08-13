'use client';

import { HeartPulse, ScanSearch, ShieldCheck } from 'lucide-react';
import { motion } from 'motion/react';
import { DOCTOR_TONE_COLOR, type DoctorTone } from '@/components/app/doctor-avatar';
import { cn } from '@/lib/shadcn/utils';

const EXPRESSIONS: { tone: DoctorTone; icon: typeof ShieldCheck; en: string; hi: string }[] = [
  { tone: 'reassuring', icon: ShieldCheck, en: 'Reassuring', hi: 'आश्वस्त' },
  { tone: 'curious', icon: ScanSearch, en: 'Curious', hi: 'उत्सुक' },
  { tone: 'concerned', icon: HeartPulse, en: 'Concerned', hi: 'चिंतित' },
];

interface ExpressionPanelProps {
  tone: DoctorTone;
  onToneChange?: (tone: DoctorTone) => void;
  className?: string;
}

/**
 * Empathy / expression indicator — the interpreted conversational tone of the
 * agent. Renders as a glass strip; the active state glows in its tone colour.
 * Also lets the caller steer the doctor's expression by tapping a state.
 */
export function ExpressionPanel({ tone, onToneChange, className }: ExpressionPanelProps) {
  return (
    <div
      className={cn('glass-panel flex items-center gap-1 rounded-full p-1.5', className)}
      role="group"
      aria-label="Agent expression"
    >
      {EXPRESSIONS.map(({ tone: id, icon: Icon, en, hi }) => {
        const active = tone === id;
        const color = DOCTOR_TONE_COLOR[id];
        return (
          <motion.button
            key={id}
            type="button"
            onClick={() => onToneChange?.(id)}
            aria-pressed={active}
            whileTap={{ scale: 0.94 }}
            className={cn(
              'flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-bold transition-all duration-300',
              active ? 'shadow-[0_0_18px_rgba(45,212,191,0.35)]' : 'text-muted-foreground'
            )}
            style={
              active
                ? { backgroundColor: `color-mix(in srgb, ${color} 22%, transparent)`, color }
                : undefined
            }
          >
            <Icon className="size-3.5" />
            <span className="hidden sm:inline">{en}</span>
            <span
              className="text-[10px] font-medium sm:hidden"
              style={{ fontFamily: 'var(--font-mukta)' }}
            >
              {hi}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}
