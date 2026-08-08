export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  // agent dispatch configuration
  agentName?: string;

  // LiveKit Cloud Sandbox configuration
  sandboxId?: string;

  // Bilingual status labels shown during a live session
  statusLabels?: {
    connecting: { en: string; hi: string };
    listening: { en: string; hi: string };
    thinking: { en: string; hi: string };
    speaking: { en: string; hi: string };
  };
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Swasthya Sahayak',
  pageTitle: 'स्वास्थ्य सहायक · Healing Garden Voice Agent',
  pageDescription:
    'A bilingual (Hindi + English) health voice agent that helps with symptoms, nearby clinics, and doctor guidance — powered by Murf Falcon TTS',

  supportsChatInput: true,
  supportsVideoInput: false,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,

  logo: '/murf-logo.svg',
  accent: '#28543D',
  logoDark: '/murf-logo-dark.svg',
  accentDark: '#93BC9B',
  startButtonText: 'Start Talking · बातचीत शुरू करें',

  statusLabels: {
    connecting: { en: 'Connecting…', hi: 'आपका स्वास्थ्य सहायक तैयार हो रहा है' },
    listening: { en: 'Listening to you', hi: 'बोलिए — मैं सुन रहा हूँ' },
    thinking: { en: 'Thinking…', hi: 'सोच रहा हूँ' },
    speaking: { en: 'I am speaking', hi: 'सुनिए — मैं बोल रहा हूँ' },
  },

  // optional: audio visualization configuration
  audioVisualizerType: 'radial',
  audioVisualizerColor: '#6B8E71',
  audioVisualizerColorDark: '#A8C3A8',
  audioVisualizerColorShift: 0.3,
  audioVisualizerRadialBarCount: 48,
  audioVisualizerRadialRadius: 110,
  audioVisualizerWaveLineWidth: 3,

  // agent dispatch configuration
  agentName: process.env.AGENT_NAME ?? undefined,

  // LiveKit Cloud Sandbox configuration
  sandboxId: undefined,
};
