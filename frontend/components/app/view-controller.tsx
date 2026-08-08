'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTheme } from 'next-themes';
import { MediaDeviceFailure } from 'livekit-client';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import { SessionEvent, useAgent, useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { CallEndedView } from '@/components/app/call-ended-view';
import { MicPermissionDialog } from '@/components/app/mic-permission-dialog';
import { WelcomeView } from '@/components/app/welcome-view';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);
const MotionCallEndedView = motion.create(CallEndedView);

const VIEW_MOTION_PROPS: MotionProps = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.4,
    ease: 'easeOut',
  },
};

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start, internal } = useSessionContext();
  const { resolvedTheme } = useTheme();
  const agent = useAgent();

  // Tracks whether the user has started a call at least once, so we can
  // distinguish the "Call ended" state from the initial "Ready" state.
  const [hasStartedCall, setHasStartedCall] = useState(false);
  const [micPermissionBlocked, setMicPermissionBlocked] = useState(false);

  const isAgentAvailable = agent.state === 'listening' || agent.state === 'speaking';

  const handleStartCall = useCallback(async () => {
    try {
      await start({ tracks: { microphone: { enabled: true } } });
      setHasStartedCall(true);
      setMicPermissionBlocked(false);
    } catch (error) {
      const failure = MediaDeviceFailure.getFailure(error);
      if (failure === MediaDeviceFailure.PermissionDenied) {
        setMicPermissionBlocked(true);
        setHasStartedCall(true);
      }
    }
  }, [start]);

  const handleRetry = useCallback(async () => {
    setMicPermissionBlocked(false);
    await handleStartCall();
  }, [handleStartCall]);

  const handleBackToHome = useCallback(() => {
    setHasStartedCall(false);
  }, []);

  // Surface microphone permission errors that happen during a live session
  // (for example when the user toggles the microphone on/off mid-call).
  useEffect(() => {
    const onMediaDeviceError = (error: Error) => {
      if (MediaDeviceFailure.getFailure(error) === MediaDeviceFailure.PermissionDenied) {
        setMicPermissionBlocked(true);
      }
    };
    internal.emitter.on(SessionEvent.MediaDevicesError, onMediaDeviceError);
    return () => {
      internal.emitter.off(SessionEvent.MediaDevicesError, onMediaDeviceError);
    };
  }, [internal.emitter]);

  // Show the session view while connected, otherwise decide between the
  // "Ready" and "Call ended" states.
  const sessionContent = useMemo(() => {
    if (isConnected) {
      return (
        <MotionSessionView
          key="session-view"
          {...VIEW_MOTION_PROPS}
          preConnectMessage={
            isAgentAvailable
              ? 'Speak now — I am listening'
              : 'Your health assistant is getting ready…'
          }
          supportsChatInput={appConfig.supportsChatInput}
          supportsVideoInput={appConfig.supportsVideoInput}
          supportsScreenShare={appConfig.supportsScreenShare}
          isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
          audioVisualizerType={appConfig.audioVisualizerType}
          audioVisualizerColor={
            resolvedTheme === 'dark'
              ? appConfig.audioVisualizerColorDark
              : appConfig.audioVisualizerColor
          }
          audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
          audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
          audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
          audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
          audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
          audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
          audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
          statusLabels={appConfig.statusLabels}
          className="fixed inset-0"
        />
      );
    }

    if (hasStartedCall) {
      return (
        <MotionCallEndedView
          key="call-ended-view"
          {...VIEW_MOTION_PROPS}
          onStartAgain={handleStartCall}
          onBackToHome={handleBackToHome}
        />
      );
    }

    return (
      <MotionWelcomeView
        key="welcome"
        {...VIEW_MOTION_PROPS}
        startButtonText={appConfig.startButtonText}
        onStartCall={handleStartCall}
      />
    );
  }, [
    isConnected,
    hasStartedCall,
    handleStartCall,
    handleBackToHome,
    isAgentAvailable,
    appConfig,
    resolvedTheme,
  ]);

  return (
    <>
      <AnimatePresence mode="wait">{sessionContent}</AnimatePresence>
      <MicPermissionDialog
        open={micPermissionBlocked}
        onClose={() => setMicPermissionBlocked(false)}
        onRetry={handleRetry}
      />
    </>
  );
}
