'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Mic } from 'lucide-react';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import {
  type AgentState,
  useAgent,
  useChat,
  useSessionContext,
  useSessionMessages,
} from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { Shimmer } from '@/components/ai-elements/shimmer';
import { type DoctorTone } from '@/components/app/doctor-avatar';
import { useLanguage } from '@/components/app/language-provider';
import { QuickLaunchCards, type QuickLaunchId } from '@/components/app/quick-launch-cards';
import { cn } from '@/lib/shadcn/utils';
import { TileLayout } from './tile-view';

const MotionMessage = motion.create(Shimmer);

const CHAT_MOTION_PROPS: MotionProps = {
  variants: {
    hidden: {
      opacity: 0,
      transition: {
        ease: 'easeOut',
        duration: 0.3,
      },
    },
    visible: {
      opacity: 1,
      transition: {
        delay: 0.2,
        ease: 'easeOut',
        duration: 0.3,
      },
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

const SHIMMER_MOTION_PROPS: MotionProps = {
  variants: {
    visible: {
      opacity: 1,
      transition: {
        ease: 'easeIn',
        duration: 0.5,
        delay: 0.8,
      },
    },
    hidden: {
      opacity: 0,
      transition: {
        ease: 'easeIn',
        duration: 0.5,
        delay: 0,
      },
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

interface AgentStatusBannerProps {
  state: AgentState;
  labels?: AppConfig['statusLabels'];
}

function ListeningIcon() {
  return (
    <span className="relative flex size-4 items-center justify-center">
      <motion.span
        aria-hidden
        animate={{ scale: [1, 1.8], opacity: [0.4, 0] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
        className="absolute inset-0 rounded-full bg-current opacity-40"
      />
      <Mic className="relative size-4" />
    </span>
  );
}

function SpeakingIcon() {
  const levels = [0.45, 0.95, 0.3, 0.8, 0.55];
  return (
    <span className="flex h-4 items-center gap-[3px]">
      {levels.map((level, i) => (
        <motion.span
          key={i}
          animate={{ scaleY: [level, 1, level], opacity: [0.45, 1, 0.45] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            repeatType: 'mirror',
            ease: 'easeInOut',
            delay: i * 0.12,
          }}
          className="h-full w-[3px] origin-center rounded-full bg-current"
          style={{ scaleY: level }}
        />
      ))}
    </span>
  );
}

function ThinkingIcon() {
  return (
    <span className="flex h-4 items-center gap-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.2, ease: 'easeInOut' }}
          className="size-1.5 rounded-full bg-current"
        />
      ))}
    </span>
  );
}

function AgentStatusBanner({ state, labels }: AgentStatusBannerProps) {
  const { language } = useLanguage();
  const info = useMemo(() => {
    switch (state) {
      case 'connecting':
      case 'initializing':
      case 'pre-connect-buffering':
        return {
          icon: <Loader2 className="size-4 animate-spin" />,
          className:
            'border-sage/30 bg-sage/10 text-forest dark:border-sage-light/25 dark:bg-sage-light/10 dark:text-sage-light',
          en: labels?.connecting.en ?? 'Connecting…',
          hi: labels?.connecting.hi ?? 'आपका स्वास्थ्य सहायक तैयार हो रहा है',
        };
      case 'listening':
        return {
          icon: <ListeningIcon />,
          className:
            'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
          en: labels?.listening.en ?? 'Listening',
          hi: labels?.listening.hi ?? 'आप बोलें — मैं सुन रहा हूँ',
        };
      case 'thinking':
        return {
          icon: <ThinkingIcon />,
          className:
            'border-gold/35 bg-gold/10 text-terracotta dark:border-gold/30 dark:bg-gold/10 dark:text-amber-200',
          en: labels?.thinking.en ?? 'Processing…',
          hi: labels?.thinking.hi ?? 'प्रोसेस हो रहा है',
        };
      case 'speaking':
        return {
          icon: <SpeakingIcon />,
          className:
            'border-peach/50 bg-peach/15 text-terracotta dark:border-peach/30 dark:bg-peach/10 dark:text-peach',
          en: labels?.speaking.en ?? 'Speaking',
          hi: labels?.speaking.hi ?? 'एजेंट बोल रहा है',
        };
      default:
        return null;
    }
  }, [state, labels]);

  if (!info) {
    return null;
  }

  const primary = language === 'hi' ? info.hi : info.en;
  const secondary = language === 'hi' ? info.en : info.hi;

  return (
    <div className="absolute top-2 left-1/2 z-40 -translate-x-1/2 md:top-4">
      <motion.div
        key={`${state}-${language}`}
        initial={{ opacity: 0, translateY: -10, scale: 0.95 }}
        animate={{ opacity: 1, translateY: 0, scale: 1 }}
        exit={{ opacity: 0, translateY: -10, scale: 0.95 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
        className={cn(
          'glass-panel flex flex-col items-center gap-0.5 rounded-2xl border px-5 py-2.5',
          info.className
        )}
      >
        <span className="flex items-center gap-2.5">
          <span className="flex items-center">{info.icon}</span>
          <span className="text-sm leading-tight font-extrabold tracking-[0.18em] uppercase md:text-base">
            {primary}
          </span>
        </span>
        <span
          className="text-xs leading-tight font-medium opacity-70"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          {secondary}
        </span>
      </motion.div>
    </div>
  );
}

interface TranscriptPanelProps {
  agentState: AgentState;
  messages: React.ComponentProps<typeof AgentChatTranscript>['messages'];
  className?: string;
}

function TranscriptPanel({ agentState, messages, className }: TranscriptPanelProps) {
  return (
    <div
      className={cn(
        'glass-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl',
        className
      )}
    >
      <div className="border-foreground/10 flex items-center justify-between border-b px-4 py-3">
        <span className="flex items-center gap-2 font-mono text-[10px] font-bold tracking-widest uppercase">
          <motion.span
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            className="size-1.5 rounded-full bg-teal-400 shadow-[0_0_8px_rgba(45,212,191,0.9)]"
          />
          Live Transcript
        </span>
        <span className="text-muted-foreground font-mono text-[10px] font-bold tracking-widest uppercase">
          EN · HI
        </span>
      </div>
      <AgentChatTranscript
        agentState={agentState}
        messages={messages}
        className="min-h-0 flex-1 [&_.is-user>div]:rounded-[22px]"
      />
    </div>
  );
}

export interface AgentSessionView_01Props {
  /**
   * Message shown above the controls before the first chat message is sent.
   *
   * @default 'Agent is listening, ask it a question'
   */
  preConnectMessage?: string;
  /**
   * Enables or disables the chat toggle and transcript input controls.
   *
   * @default true
   */
  supportsChatInput?: boolean;
  /**
   * Enables or disables camera controls in the bottom control bar.
   *
   * @default true
   */
  supportsVideoInput?: boolean;
  /**
   * Enables or disables screen sharing controls in the bottom control bar.
   *
   * @default true
   */
  supportsScreenShare?: boolean;
  /**
   * Shows a pre-connect buffer state with a shimmer message before messages appear.
   *
   * @default true
   */
  isPreConnectBufferEnabled?: boolean;

  /** Selects the visualizer style rendered in the main tile area. */
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  /** Primary hex color used by supported audio visualizer variants. */
  audioVisualizerColor?: `#${string}`;
  /** Hue shift intensity used by certain visualizers. */
  audioVisualizerColorShift?: number;
  /** Number of bars to render when `audioVisualizerType` is `bar`. */
  audioVisualizerBarCount?: number;
  /** Number of rows in the visualizer when `audioVisualizerType` is `grid`. */
  audioVisualizerGridRowCount?: number;
  /** Number of columns in the visualizer when `audioVisualizerType` is `grid`. */
  audioVisualizerGridColumnCount?: number;
  /** Number of radial bars when `audioVisualizerType` is `radial`. */
  audioVisualizerRadialBarCount?: number;
  /** Base radius of the radial visualizer when `audioVisualizerType` is `radial`. */
  audioVisualizerRadialRadius?: number;
  /** Stroke width of the wave path when `audioVisualizerType` is `wave`. */
  audioVisualizerWaveLineWidth?: number;
  /** Bilingual status labels shown in the live status banner. */
  statusLabels?: AppConfig['statusLabels'];
  /** Optional class name merged onto the outer `<section>` container. */
  className?: string;
}

export function AgentSessionView_01({
  preConnectMessage = 'Agent is listening, ask it a question',
  supportsChatInput = true,
  supportsVideoInput = true,
  supportsScreenShare = true,
  isPreConnectBufferEnabled = true,

  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerWaveLineWidth,
  statusLabels,
  ref,
  className,
  ...props
}: React.ComponentProps<'section'> & AgentSessionView_01Props) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const [chatOpen, setChatOpen] = useState(false);
  const [tone, setTone] = useState<DoctorTone | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { state: agentState } = useAgent();
  const { send } = useChat();

  // Expression tone — caller can steer it manually; otherwise derived from state.
  const toneValue: DoctorTone = tone ?? (agentState === 'thinking' ? 'curious' : 'reassuring');

  // Context-aware quick actions — fire the matching tool-path by sending a
  // chat message to the agent, mirroring the spoken intent.
  const handleQuickLaunch = useCallback(
    (id: QuickLaunchId) => {
      void send(
        id === 'clinic'
          ? 'Can you help me find a nearby clinic?'
          : 'Can you check my symptom history?'
      );
    },
    [send]
  );

  const controls: AgentControlBarControls = {
    leave: true,
    microphone: true,
    chat: supportsChatInput,
    camera: supportsVideoInput,
    screenShare: supportsScreenShare,
  };

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <section ref={ref} className={cn('relative z-10 w-full overflow-hidden', className)} {...props}>
      <Fade top className="absolute inset-x-4 top-0 z-10 h-40" />
      {/* Live status banner (connecting / listening / speaking) */}
      <AgentStatusBanner state={agentState} labels={statusLabels} />

      {/* Dashboard row — stage + persistent transcript column (lg+) */}
      <div className="absolute inset-0 z-20 flex">
        {/* Main stage — natural flow so the robot, quick actions and dock never overlap */}
        <div className="relative flex h-full min-w-0 flex-1 flex-col">
          {/* Robot stage */}
          <div className="flex min-h-0 w-full flex-1 items-center justify-center">
            <TileLayout
              chatOpen={false}
              tone={toneValue}
              onToneChange={setTone}
              audioVisualizerType={audioVisualizerType}
              audioVisualizerColor={audioVisualizerColor}
              audioVisualizerColorShift={audioVisualizerColorShift}
              audioVisualizerBarCount={audioVisualizerBarCount}
              audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
              audioVisualizerRadialRadius={audioVisualizerRadialRadius}
              audioVisualizerGridRowCount={audioVisualizerGridRowCount}
              audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
              audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
            />
          </div>

          {/* Context-aware quick actions */}
          <AnimatePresence>
            {!chatOpen && (
              <motion.div
                key="quick-actions"
                initial={{ opacity: 0, translateY: 16 }}
                animate={{ opacity: 1, translateY: 0 }}
                exit={{ opacity: 0, translateY: 16 }}
                transition={{ duration: 0.4, ease: 'easeOut', delay: 0.5 }}
                className="flex justify-center px-4 pt-1 pb-2"
              >
                <QuickLaunchCards compact onSelect={handleQuickLaunch} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Bottom dock — always visible, no slide animation */}
          <div className="relative shrink-0 px-3 pb-3 md:px-8 md:pb-6">
            {/* Pre-connect message */}
            {isPreConnectBufferEnabled && (
              <AnimatePresence>
                {messages.length === 0 && (
                  <MotionMessage
                    key="pre-connect-message"
                    duration={2}
                    aria-hidden={messages.length > 0}
                    {...SHIMMER_MOTION_PROPS}
                    className="pointer-events-none mx-auto block w-full max-w-2xl pb-4 text-center text-sm font-semibold"
                  >
                    {preConnectMessage}
                  </MotionMessage>
                )}
              </AnimatePresence>
            )}
            <div className="relative mx-auto max-w-2xl">
              <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
              <AgentControlBar
                variant="livekit"
                controls={controls}
                isChatOpen={chatOpen}
                isConnected={session.isConnected}
                onDisconnect={session.end}
                onIsChatOpenChange={setChatOpen}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Transcript — shown ONLY when the user taps the chat/transcript toggle */}
      <AnimatePresence>
        {chatOpen && (
          <motion.div
            {...CHAT_MOTION_PROPS}
            className="absolute inset-x-3 top-20 bottom-[180px] z-[60] flex xl:top-16 xl:right-6 xl:bottom-16 xl:left-auto xl:w-[340px]"
          >
            <TranscriptPanel agentState={agentState} messages={messages} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
