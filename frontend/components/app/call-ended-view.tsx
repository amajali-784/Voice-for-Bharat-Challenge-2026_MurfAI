'use client';

import { ArrowLeft, HeartHandshake, RotateCcw } from 'lucide-react';
import { motion } from 'motion/react';
import { AuroraGlow, BotanicalLeaves, TwinklingStars } from '@/components/app/garden-decor';
import { HealingCircle } from '@/components/app/healing-circle';
import { Button } from '@/components/ui/button';

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.05,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16, scale: 0.97 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: 'spring' as const, stiffness: 220, damping: 24 },
  },
};

interface CallEndedViewProps {
  onStartAgain: () => void;
  onBackToHome: () => void;
}

export const CallEndedView = ({
  onStartAgain,
  onBackToHome,
  ref,
}: React.ComponentProps<'div'> & CallEndedViewProps) => {
  return (
    <div ref={ref} className="bg-background relative flex min-h-svh flex-col overflow-hidden">
      <div className="botanical-bg pointer-events-none absolute inset-0" aria-hidden />
      <BotanicalLeaves />
      <AuroraGlow />
      <TwinklingStars count={10} />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="relative flex grow flex-col items-center justify-center px-4 py-14 text-center"
      >
        <motion.div variants={itemVariants}>
          <HealingCircle state="ended" size="clamp(190px, 46vw, 250px)" />
        </motion.div>

        <motion.h1
          variants={itemVariants}
          className="mt-6 text-3xl leading-tight font-bold tracking-tight md:text-4xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          Conversation Complete 🌿
          <span className="text-muted-foreground mt-2 block text-lg font-semibold md:text-xl">
            बातचीत पूरी हुई
          </span>
        </motion.h1>

        <motion.p
          variants={itemVariants}
          className="text-muted-foreground mt-5 max-w-prose leading-7 font-medium"
        >
          Hope I could help. Take care — your health matters most. ❤️
        </motion.p>
        <motion.p
          variants={itemVariants}
          className="text-muted-foreground mt-1.5 max-w-prose text-sm"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          उम्मीद है मैं आपकी मदद कर पाया। अपना ख्याल रखें — आपका स्वास्थ्य ही सबसे बड़ा धन है।
        </motion.p>

        <motion.div variants={itemVariants} className="mt-9 flex flex-col items-center gap-3">
          <Button
            size="lg"
            onClick={onStartAgain}
            className="group relative w-80 overflow-hidden rounded-full bg-gradient-to-b from-[#3a7353] to-[#234236] px-8 py-7 font-mono text-sm font-bold tracking-wider text-[var(--primary-foreground)] uppercase shadow-[0_18px_40px_-12px_rgba(35,66,54,0.6),inset_0_1px_0_rgba(255,255,255,0.25)] transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[0_8px_18px_-8px_rgba(35,66,54,0.6)]"
          >
            <span
              aria-hidden
              className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
            />
            <motion.span
              animate={{ rotate: [0, -20, 0, 12, 0] }}
              transition={{ duration: 3, repeat: Infinity, repeatDelay: 2.5, ease: 'easeInOut' }}
              className="relative"
            >
              <RotateCcw className="size-5" />
            </motion.span>
            <span className="relative">Talk Again · फिर से बात करें</span>
          </Button>

          <Button
            size="lg"
            variant="outline"
            onClick={onBackToHome}
            className="group border-sage/40 w-80 rounded-full px-8 py-6 font-mono text-xs font-bold tracking-wider uppercase"
          >
            <ArrowLeft className="size-4 transition-transform duration-300 group-hover:-translate-x-1" />
            Back to Home · होम पर वापस जाएँ
          </Button>
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8, duration: 0.8 }}
        className="relative flex w-full items-center justify-center px-4 pb-6"
      >
        <p className="text-muted-foreground flex max-w-prose items-center justify-center gap-1.5 pt-1 text-center text-xs leading-5 font-normal text-pretty md:text-sm">
          <HeartHandshake className="text-sage size-3.5 shrink-0" />
          For serious symptoms, call 108 or go to your nearest hospital immediately.
        </p>
      </motion.div>
    </div>
  );
};
