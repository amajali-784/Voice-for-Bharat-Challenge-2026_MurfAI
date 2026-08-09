import path from 'path';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  eslint: {
    // These warnings come from upstream LiveKit/AI UI components, not our code.
    ignoreDuringBuilds: true,
  },
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
