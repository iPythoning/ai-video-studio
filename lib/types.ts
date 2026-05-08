export const languages = ["zh", "en"] as const;
export const platforms = ["tiktok", "reels", "shorts"] as const;

export type Language = (typeof languages)[number];
export type Platform = (typeof platforms)[number];
export type AssetKind = "image" | "video" | "audio" | "reference" | "brand" | "unknown";
export type JobStatus = "queued" | "rendering" | "completed" | "failed";

export type ProjectBrief = {
  productName: string;
  targetAudience: string;
  sellingPoints: string;
  tone: string;
  sourceScript: string;
  scenario: string;
  generationMode: "local" | "api";
  forbiddenWords: string[];
  targetPlatforms: Platform[];
};

export type AssetItem = {
  id: string;
  kind: AssetKind;
  fileName: string;
  path: string;
  mimeType: string;
  sizeBytes: number;
  durationSec?: number;
  width?: number;
  height?: number;
  status: "ready" | "needs-review";
};

export type AssetManifest = {
  projectId: string;
  createdAt: string;
  assets: AssetItem[];
  referenceAssetId?: string;
};

export type StyleBlueprint = {
  projectId: string;
  source: "reference-video" | "default-local";
  targetDurationSec: number;
  hookType: "problem" | "surprise" | "proof" | "question";
  sceneCount: number;
  avgShotLengthSec: number;
  captionPosition: "center-safe" | "lower-third-safe";
  captionEmphasis: "keyword-pop" | "word-highlight";
  bRollDensity: "low" | "medium" | "high";
  audioMix: {
    voiceDb: number;
    musicDb: number;
  };
  ctaAtSec: number;
  safeZone: {
    topPx: number;
    rightPx: number;
    bottomPx: number;
    leftPx: number;
  };
};

export type StoryboardScene = {
  id: string;
  startSec: number;
  durationSec: number;
  narration: string;
  caption: string;
  assetId?: string;
  transition: "cut" | "push" | "flash";
};

export type Storyboard = {
  projectId: string;
  language: Language;
  variant: number;
  platform: Platform;
  width: 1080;
  height: 1920;
  fps: 30;
  scenes: StoryboardScene[];
  title: string;
  description: string;
  hashtags: string[];
  seedanceClips?: string[];
  voiceoverPath?: string;
};

export type RenderJob = {
  id: string;
  projectId: string;
  language: Language;
  platform: Platform;
  variant: number;
  status: JobStatus;
  outputPath?: string;
  srtPath?: string;
  coverPath?: string;
  reportPath?: string;
  error?: string;
};

export type ProjectRecord = {
  id: string;
  createdAt: string;
  brief: ProjectBrief;
  manifest: AssetManifest;
  blueprint?: StyleBlueprint;
  storyboards: Storyboard[];
  jobs: RenderJob[];
};

export type AdapterSet = {
  transcribe: (asset: AssetItem) => Promise<string>;
  translate: (text: string, language: Language) => Promise<string>;
  tts: (text: string, language: Language) => Promise<{audioPath?: string; durationSec: number}>;
  scriptRewrite: (brief: ProjectBrief, language: Language, variant: number) => Promise<string>;
  shotPrompts: (storyboard: Storyboard, brief: ProjectBrief) => Promise<string[]>;
  visualAnalyze: (manifest: AssetManifest) => Promise<StyleBlueprint>;
  generateVideoClips: (prompts: string[], storyboard: Storyboard, outputDir: string) => Promise<string[]>;
  render: (storyboard: Storyboard, job: RenderJob, outputDir: string) => Promise<RenderJob>;
};
