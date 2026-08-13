'use client';

import { Mic } from 'lucide-react';
import { motion } from 'motion/react';
import { HealingCircle } from '@/components/app/healing-circle';
import { QuickLaunchCards } from '@/components/app/quick-launch-cards';
import { Button } from '@/components/ui/button';

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 18, scale: 0.97 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: 'spring' as const, stiffness: 220, damping: 24 },
  },
};

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div
      ref={ref}
      className="scroll-if-needed relative flex min-h-svh flex-col pt-[84px] md:pt-[92px]"
    >
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="relative flex grow flex-col items-center justify-center px-4 py-5 text-center md:py-8"
      >
        <motion.span
          variants={itemVariants}
          className="glass-chip text-foreground/80 mb-3 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 font-mono text-[11px] font-bold tracking-wider uppercase shadow-sm"
        >
          <motion.span
            animate={{ opacity: [1, 0.3, 1], scale: [1, 1.4, 1] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
            className="size-1.5 rounded-full bg-teal-400 shadow-[0_0_10px_rgba(45,212,191,0.9)]"
          />
          ✨ Ready · तैयार
        </motion.span>

        <motion.div variants={itemVariants}>
          <HealingCircle state="ready" size="clamp(150px, 23vh, 240px)" />
        </motion.div>

        <motion.h1
          variants={itemVariants}
          className="mt-1 text-3xl leading-tight font-bold tracking-tight md:text-4xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          <span>Your Health,</span>{' '}
          <span className="animate-shimmer text-glow bg-[linear-gradient(110deg,#2dd4bf,#38bdf8,#5eead4,#2dd4bf)] bg-[length:220%_auto] bg-clip-text text-transparent">
            Your Voice.
          </span>
        </motion.h1>

        <motion.p
          variants={itemVariants}
          className="text-muted-foreground mt-1 text-lg font-semibold md:text-xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          आपकी सेहत, आपकी आवाज़।
        </motion.p>

        <motion.p
          variants={itemVariants}
          className="short-hidden text-muted-foreground mt-2 max-w-prose leading-6 font-medium"
        >
          Speak naturally to understand symptoms, find nearby care, and get guidance before you
          visit a doctor — comfortably in Hindi or English.
        </motion.p>

        <motion.div variants={itemVariants} className="mt-3">
          <Button
            size="lg"
            onClick={onStartCall}
            className="group relative w-72 overflow-hidden rounded-full bg-gradient-to-b from-[#2dd4bf] to-[#0891b2] px-8 py-5 font-mono text-sm font-bold tracking-wider text-[#04201a] uppercase shadow-[0_18px_40px_-12px_rgba(45,212,191,0.6),inset_0_1px_0_rgba(255,255,255,0.35)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_24px_50px_-12px_rgba(45,212,191,0.75),inset_0_1px_0_rgba(255,255,255,0.35)] active:translate-y-0.5 active:shadow-[0_8px_18px_-8px_rgba(45,212,191,0.6),inset_0_1px_0_rgba(255,255,255,0.35)]"
          >
            <span
              aria-hidden
              className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/40 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
            />
            <motion.span
              animate={{ rotate: [0, 20, 0, -12, 0] }}
              transition={{ duration: 3, repeat: Infinity, repeatDelay: 2.5, ease: 'easeInOut' }}
              className="relative"
            >
              <Mic className="size-5" />
            </motion.span>
            <span className="relative">{startButtonText}</span>
          </Button>
        </motion.div>

        <motion.div
          variants={itemVariants}
          className="mt-4 flex w-full flex-col items-center gap-2"
        >
          <span className="short-hidden text-muted-foreground font-mono text-[10px] font-bold tracking-widest uppercase">
            Quick actions · तेज़ कार्रवाई
          </span>
          <div className="hidden min-[640px]:block">
            <QuickLaunchCards onSelect={onStartCall} />
          </div>
          <div className="min-[640px]:hidden">
            <QuickLaunchCards compact onSelect={onStartCall} />
          </div>
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.8 }}
        className="relative flex w-full items-center justify-center px-4 pb-3"
      >
        <p className="short-hidden text-muted-foreground max-w-prose pt-1 text-center text-xs leading-5 font-normal text-pretty md:text-sm">
          <span className="font-semibold">Health companion, not a doctor.</span> For serious
          symptoms, call your nearest hospital or 108 immediately.
          <span className="text-muted-foreground/70 mt-1 block text-[10px]">
            ध्यान दें: यह एजेंट जानकारी के लिए है, डॉक्टर नहीं। गंभीर लक्षण होने पर तुरंत 108 पर कॉल
            करें।
          </span>
        </p>
      </motion.div>
    </div>
  );
};
