import {NextResponse} from "next/server";
import {hasFishAudioConfig, hasSeedanceConfig} from "@/lib/adapters/external";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({
    integrations: {
      seedance: {
        configured: hasSeedanceConfig(),
        model: process.env.SEEDANCE_MODEL || "doubao-seedance-2-0-260128",
        maxClipsPerStoryboard: Number(process.env.SEEDANCE_MAX_CLIPS || 3),
      },
      fishAudio: {
        configured: hasFishAudioConfig(),
        model: process.env.FISH_AUDIO_MODEL || "s2-pro",
        zhVoiceConfigured: Boolean(process.env.FISH_AUDIO_VOICE_ZH),
        enVoiceConfigured: Boolean(process.env.FISH_AUDIO_VOICE_EN),
      },
    },
  });
}
