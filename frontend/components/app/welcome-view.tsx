'use client';

import { Activity, MapPin, MessagesSquare, Mic } from 'lucide-react';
import { motion } from 'motion/react';
import {
  AuroraGlow,
  BotanicalLeaves,
  FloatingParticles,
  TwinklingStars,
} from '@/components/app/garden-decor';
import { HealingCircle } from '@/components/app/healing-circle';
import { TiltCard } from '@/components/app/tilt-card';
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

const FEATURES = [
  {
    icon: Activity,
    en: 'Understand Symptoms',
    hi: 'लक्षण समझें',
  },
  {
    icon: MapPin,
    en: 'Find Nearby Care',
    hi: 'नज़दीकी देखभाल खोजें',
  },
  {
    icon: MessagesSquare,
    en: 'Doctor Guidance',
    hi: 'डॉक्टर मार्गदर्शन',
  },
];

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
    <div ref={ref} className="bg-background relative flex min-h-svh flex-col overflow-hidden">
      {/* Magical garden backdrop */}
      <div className="botanical-bg pointer-events-none absolute inset-0" aria-hidden />
      <BotanicalLeaves />
      <AuroraGlow />
      <TwinklingStars count={16} />
      <FloatingParticles count={14} />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="relative flex grow flex-col items-center justify-center px-4 py-14 text-center"
      >
        <motion.span
          variants={itemVariants}
          className="border-gold/30 bg-cream/60 dark:bg-forest/40 mb-6 inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 font-mono text-[11px] font-bold tracking-wider uppercase shadow-sm backdrop-blur"
        >
          <motion.span
            animate={{ opacity: [1, 0.3, 1], scale: [1, 1.4, 1] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
            className="bg-gold size-1.5 rounded-full"
          />
          ✨ Healing Garden · #VoiceForBharat
        </motion.span>

        <motion.div variants={itemVariants}>
          <HealingCircle state="ready" />
        </motion.div>

        <motion.p
          variants={itemVariants}
          className="text-muted-foreground mt-3 text-sm font-medium"
        >
          🙏 Namaste — I&apos;m Dr. Swasthya, your voice companion.
        </motion.p>

        <motion.h1
          variants={itemVariants}
          className="mt-4 text-4xl leading-tight font-bold tracking-tight md:text-6xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          <span>Your Health,</span>{' '}
          <span className="animate-shimmer bg-[linear-gradient(110deg,#234236,#6b8e71,#d9a441,#234236)] bg-[length:220%_auto] bg-clip-text text-transparent">
            Your Voice.
          </span>
        </motion.h1>

        <motion.p
          variants={itemVariants}
          className="text-muted-foreground mt-2 text-lg font-semibold md:text-xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          आपकी सेहत, आपकी आवाज़।
        </motion.p>

        <motion.p
          variants={itemVariants}
          className="text-muted-foreground mt-4 max-w-prose leading-7 font-medium"
        >
          Speak naturally to understand symptoms, find nearby care, and get guidance before you
          visit a doctor — comfortably in Hindi or English.
        </motion.p>

        <motion.div variants={itemVariants} className="mt-8">
          <Button
            size="lg"
            onClick={onStartCall}
            className="group relative w-80 overflow-hidden rounded-full bg-gradient-to-b from-[#3a7353] to-[#234236] px-8 py-7 font-mono text-sm font-bold tracking-wider text-[var(--primary-foreground)] uppercase shadow-[0_18px_40px_-12px_rgba(35,66,54,0.6),inset_0_1px_0_rgba(255,255,255,0.25)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_24px_50px_-12px_rgba(35,66,54,0.7),inset_0_1px_0_rgba(255,255,255,0.25)] active:translate-y-0.5 active:shadow-[0_8px_18px_-8px_rgba(35,66,54,0.6),inset_0_1px_0_rgba(255,255,255,0.25)]"
          >
            <span
              aria-hidden
              className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
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
          <p className="text-muted-foreground mt-4 text-xs">
            बातचीत शुरू करें · English • हिंदी · A working microphone is needed to talk.
          </p>
        </motion.div>

        <motion.div
          variants={itemVariants}
          className="mt-9 flex flex-wrap items-stretch justify-center gap-3"
        >
          {FEATURES.map(({ icon: Icon, en, hi }) => (
            <TiltCard
              key={en}
              className="border-border/80 bg-card/70 dark:bg-forest/30 rounded-2xl shadow-[0_10px_30px_-15px_rgba(35,66,54,0.4)] backdrop-blur"
            >
              <div className="flex w-40 flex-col items-center gap-2 px-4 py-4 md:w-44">
                <span className="from-sage to-forest text-cream dark:from-sage-light dark:to-forest flex size-10 items-center justify-center rounded-full bg-gradient-to-b shadow-md">
                  <Icon className="size-5" />
                </span>
                <span className="text-sm font-bold">{en}</span>
                <span
                  className="text-muted-foreground text-[11px]"
                  style={{ fontFamily: 'var(--font-mukta)' }}
                >
                  {hi}
                </span>
              </div>
            </TiltCard>
          ))}
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.8 }}
        className="relative flex w-full items-center justify-center px-4 pb-6"
      >
        <p className="text-muted-foreground max-w-prose pt-1 text-center text-xs leading-5 font-normal text-pretty md:text-sm">
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
