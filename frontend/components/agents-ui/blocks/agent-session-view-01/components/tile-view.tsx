import React, { useMemo } from 'react';
import { Track } from 'livekit-client';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import {
  type TrackReference,
  VideoTrack,
  useLocalParticipant,
  useTracks,
  useVoiceAssistant,
} from '@livekit/components-react';
import { DoctorAvatar, type DoctorState, type DoctorTone } from '@/components/app/doctor-avatar';
import { ExpressionPanel } from '@/components/app/expression-panel';
import { AudioVisualizer } from './audio-visualizer';

const ANIMATION_TRANSITION: MotionProps['transition'] = {
  type: 'spring',
  stiffness: 675,
  damping: 75,
  mass: 1,
};

export function useLocalTrackRef(source: Track.Source) {
  const { localParticipant } = useLocalParticipant();
  const publication = localParticipant.getTrackPublication(source);
  const trackRef = useMemo<TrackReference | undefined>(
    () => (publication ? { source, participant: localParticipant, publication } : undefined),
    [source, publication, localParticipant]
  );
  return trackRef;
}

interface TileLayoutProps {
  chatOpen: boolean;
  tone: DoctorTone;
  onToneChange?: (tone: DoctorTone) => void;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerWaveLineWidth?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerBarCount?: number;
}

/**
 * The voice-call stage. Uses a vmin-sized circular stage (no fixed pixel
 * sizes) so the doctor + ring stay centred and never overflow the screen; the
 * visualizer is clipped inside the circle instead of being clipped by it.
 */
export function TileLayout({
  chatOpen,
  tone,
  onToneChange,
  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerWaveLineWidth,
}: TileLayoutProps) {
  const { videoTrack: agentVideoTrack, state: agentAssistantState } = useVoiceAssistant();
  const [screenShareTrack] = useTracks([Track.Source.ScreenShare]);
  const cameraTrack: TrackReference | undefined = useLocalTrackRef(Track.Source.Camera);

  const isCameraEnabled = cameraTrack && !cameraTrack.publication.isMuted;
  const isScreenShareEnabled = screenShareTrack && !screenShareTrack.publication.isMuted;
  const hasSecondTile = isCameraEnabled || isScreenShareEnabled;

  const doctorState: DoctorState =
    agentAssistantState === 'speaking'
      ? 'speaking'
      : agentAssistantState === 'listening'
        ? 'listening'
        : agentAssistantState === 'thinking'
          ? 'thinking'
          : 'ready';

  const isAvatar = agentVideoTrack !== undefined;
  const videoWidth = agentVideoTrack?.publication.dimensions?.width ?? 0;
  const videoHeight = agentVideoTrack?.publication.dimensions?.height ?? 0;

  return (
    <div className="relative h-full w-full">
      {/* Stage — flex-centred, clipped so the ring never overflows the screen */}
      <div className="absolute inset-0 flex items-center justify-center overflow-hidden px-4 md:px-8">
        {/* Healing halo behind everything */}
        <div
          aria-hidden
          className="absolute top-1/2 left-1/2 size-[min(80vw,360px)] -translate-x-1/2 -translate-y-1/2 rounded-full blur-2xl md:size-[min(46vw,480px)]"
          style={{
            background:
              'radial-gradient(circle at center, color-mix(in srgb, #2dd4bf 20%, transparent), transparent 70%)',
          }}
        />

        <AnimatePresence mode="popLayout">
          {!isAvatar ? (
            <motion.div
              key="agent"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ ...ANIMATION_TRANSITION, delay: 0.15 }}
              className="relative flex flex-col items-center"
            >
              {/* Circular stage — sized to fit BOTH dimensions so it never overflows */}
              <div className="relative aspect-square w-[min(84vw,50vh,400px)] md:w-[min(72vw,54vh,540px)]">
                {/* Audio visualizer — clipped inside the circle, scaled to fit */}
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-0 overflow-hidden rounded-full"
                >
                  <div className="absolute inset-0 grid place-items-center">
                    <div className="scale-[0.9] sm:scale-100 md:scale-[1.2] xl:scale-[1.6]">
                      <AudioVisualizer
                        audioVisualizerType={audioVisualizerType}
                        audioVisualizerColor={audioVisualizerColor}
                        audioVisualizerColorShift={audioVisualizerColorShift}
                        audioVisualizerBarCount={audioVisualizerBarCount}
                        audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
                        audioVisualizerRadialRadius={audioVisualizerRadialRadius}
                        audioVisualizerGridRowCount={audioVisualizerGridRowCount}
                        audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
                        audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
                        isChatOpen={chatOpen}
                        className="border-transparent bg-transparent"
                        style={{ color: audioVisualizerColor }}
                      />
                    </div>
                  </div>
                </div>

                {/* Glass disc behind the doctor — a clear, centred focus */}
                <div
                  aria-hidden
                  className="absolute inset-[20%] rounded-full border border-white/15 bg-white/5 shadow-[0_10px_40px_-12px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.15)] backdrop-blur-sm"
                />

                {/* The doctor — centred in the disc, scaled with the stage */}
                <div className="absolute inset-0 grid place-items-center">
                  <div className="w-[52%]">
                    <DoctorAvatar state={doctorState} tone={tone} />
                  </div>
                </div>
              </div>

              {/* Empathy / expression panel */}
              <div className="relative mt-3 sm:mt-4">
                <ExpressionPanel tone={tone} onToneChange={onToneChange} />
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="avatar"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ ...ANIMATION_TRANSITION, delay: 0.15 }}
              className="relative overflow-hidden rounded-2xl bg-black drop-shadow-xl/80"
            >
              <VideoTrack
                width={videoWidth}
                height={videoHeight}
                trackRef={agentVideoTrack}
                className="h-full w-full object-cover"
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Camera / screen-share chip — tucked below the header, clear of the transcript */}
      <AnimatePresence>
        {hasSecondTile && (
          <motion.div
            key="camera"
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0 }}
            transition={ANIMATION_TRANSITION}
            className="absolute top-2 right-2 z-10 md:top-4 md:right-6"
          >
            <VideoTrack
              trackRef={cameraTrack || screenShareTrack}
              width={(cameraTrack || screenShareTrack)?.publication.dimensions?.width ?? 0}
              height={(cameraTrack || screenShareTrack)?.publication.dimensions?.height ?? 0}
              className="bg-muted aspect-square size-20 rounded-lg object-cover md:size-24"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
