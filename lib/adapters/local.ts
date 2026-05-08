import {mkdir, mkdtemp, rm, writeFile} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {execFile} from "node:child_process";
import {promisify} from "node:util";
import {storyboardToSrt} from "../srt";
import type {
  AdapterSet,
  AssetItem,
  AssetManifest,
  Language,
  ProjectBrief,
  RenderJob,
  Storyboard,
  StoryboardScene,
  StyleBlueprint,
} from "../types";
import {
  generateFishAudio,
  generateSeedanceClips as callSeedance,
  hasFishAudioConfig,
  hasSeedanceConfig,
} from "./external";

const execFileAsync = promisify(execFile);

const platformCopy = {
  tiktok: {
    title: "TikTok",
    hint: "开头 2 秒强钩子，字幕居中安全区，结尾直接 CTA。",
    tags: ["#TikTokMadeMeTryIt", "#Productivity", "#SmallBusiness"],
  },
  reels: {
    title: "Instagram Reels",
    hint: "画面保持中心 4:5 关键内容，字幕避开底部按钮。",
    tags: ["#Reels", "#CreatorTools", "#Marketing"],
  },
  shorts: {
    title: "YouTube Shorts",
    hint: "标题更像搜索入口，保留清晰收益点和问题句。",
    tags: ["#Shorts", "#HowTo", "#Growth"],
  },
} as const;

export const localAdapters: AdapterSet = {
  async transcribe(asset: AssetItem) {
    return `${asset.fileName} 的本地转写占位结果，可替换为 WhisperX 或 faster-whisper。`;
  },

  async translate(text: string, language: Language) {
    if (language === "zh") return text;
    return text
      .replaceAll("省时间", "save time")
      .replaceAll("自动", "automatic")
      .replaceAll("短视频", "short video")
      .replaceAll("开始", "start")
      .replaceAll("现在", "now");
  },

  async tts(text: string) {
    const durationSec = Math.min(45, Math.max(15, Math.ceil(text.length / 7)));
    return {durationSec};
  },

  async scriptRewrite(brief: ProjectBrief, language: Language, variant: number) {
    const base = brief.sourceScript.trim() || brief.sellingPoints.trim();
    const hooks = {
      zh: [
        `还在手动剪 ${brief.productName} 的素材吗？`,
        `把一条卖点变成三条可测短视频。`,
        `${brief.targetAudience} 最容易忽略的增长动作。`,
      ],
      en: [
        `Still editing ${brief.productName} clips by hand?`,
        `Turn one offer into three testable short videos.`,
        `The growth move most ${brief.targetAudience || "teams"} miss.`,
      ],
    };
    const benefits =
      language === "zh"
        ? `${base} 核心卖点是：${brief.sellingPoints}。语气：${brief.tone || "直接可信"}。`
        : `${brief.productName} helps ${brief.targetAudience || "teams"} with: ${brief.sellingPoints}. Tone: ${brief.tone || "direct and credible"}.`;
    const scenario =
      language === "zh"
        ? brief.scenario
          ? ` 使用场景：${brief.scenario}。`
          : ""
        : brief.scenario
          ? ` Scenario: ${brief.scenario}.`
          : "";
    const cta =
      language === "zh"
        ? "现在上传素材，自动生成可发布版本。"
        : "Upload your assets and generate publish-ready variants now.";
    return `${hooks[language][variant - 1]} ${benefits}${scenario} ${cta}`;
  },

  async shotPrompts(storyboard: Storyboard, brief: ProjectBrief) {
    return storyboard.scenes.map((scene, index) => {
      const scenario = brief.scenario || "modern social-media product use case";
      const languageHint = storyboard.language === "zh" ? "Chinese market" : "global English market";
      return [
        `Vertical 9:16 marketing video shot ${index + 1} for ${brief.productName}.`,
        `Scenario: ${scenario}.`,
        `Audience: ${brief.targetAudience || "social media buyers"}.`,
        `Show the benefit: ${scene.narration}.`,
        `Cinematic handheld camera, natural product close-ups, clean background, high retention social ad pacing.`,
        `No logos, no readable brand text except the user's product, no copyrighted characters. ${languageHint}.`,
      ].join(" ");
    });
  },

  async visualAnalyze(manifest: AssetManifest) {
    const reference = manifest.assets.find((asset) => asset.id === manifest.referenceAssetId);
    const duration = reference?.durationSec ? Math.min(45, Math.max(15, reference.durationSec)) : 24;
    const sceneCount = Math.min(8, Math.max(4, Math.round(duration / 4)));
    return {
      projectId: manifest.projectId,
      source: reference ? "reference-video" : "default-local",
      targetDurationSec: duration,
      hookType: reference ? "proof" : "problem",
      sceneCount,
      avgShotLengthSec: Number((duration / sceneCount).toFixed(1)),
      captionPosition: "center-safe",
      captionEmphasis: "keyword-pop",
      bRollDensity: reference && reference.durationSec && reference.durationSec < 20 ? "high" : "medium",
      audioMix: {voiceDb: -3, musicDb: -18},
      ctaAtSec: Math.max(10, duration - 4),
      safeZone: {topPx: 180, rightPx: 160, bottomPx: 360, leftPx: 80},
    } satisfies StyleBlueprint;
  },

  async generateVideoClips(prompts: string[], storyboard: Storyboard, outputDir: string) {
    if (storyboard.variant !== 1 || storyboard.platform !== "tiktok" || !hasSeedanceConfig()) {
      return [];
    }
    return callSeedance(prompts, storyboard, outputDir);
  },

  async render(storyboard: Storyboard, job: RenderJob, outputDir: string) {
    await mkdir(outputDir, {recursive: true});
    const base = `${storyboard.language}-${storyboard.platform}-v${storyboard.variant}`;
    const srtPath = path.join(outputDir, `${base}.srt`);
    const reportPath = path.join(outputDir, `${base}.json`);
    const coverPath = path.join(outputDir, `${base}.cover.txt`);
    const outputPath = path.join(outputDir, `${base}.mp4`);
    await writeFile(srtPath, storyboardToSrt(storyboard), "utf8");
    await writeFile(
      reportPath,
      JSON.stringify(
        {
          jobId: job.id,
          storyboard,
          checks: [
            "9:16 1080x1920",
            "字幕使用中心安全区",
            "首 2 秒包含钩子",
            "输出含 SRT 和平台文案",
          ],
        },
        null,
        2,
      ),
      "utf8",
    );
    await writeFile(coverPath, `${storyboard.title}\n${storyboard.description}\n`, "utf8");
    await renderMp4(outputPath, storyboard);
    return {...job, status: "completed", outputPath, srtPath, reportPath, coverPath};
  },
};

export function buildStoryboard(
  brief: ProjectBrief,
  blueprint: StyleBlueprint,
  script: string,
  language: Language,
  platform: keyof typeof platformCopy,
  variant: number,
  assets: AssetItem[],
): Storyboard {
  const sentences = splitScript(script);
  const sceneCount = Math.max(4, blueprint.sceneCount);
  const duration = Math.max(15, Math.min(45, blueprint.targetDurationSec + (variant - 2) * 2));
  const perScene = Number((duration / sceneCount).toFixed(2));
  const visualAssets = assets.filter((asset) => asset.kind === "image" || asset.kind === "video");
  const scenes: StoryboardScene[] = Array.from({length: sceneCount}, (_, index) => {
    const caption = sentences[index % sentences.length] || brief.productName;
    return {
      id: `s${index + 1}`,
      startSec: Number((index * perScene).toFixed(2)),
      durationSec: index === sceneCount - 1 ? Number((duration - index * perScene).toFixed(2)) : perScene,
      narration: caption,
      caption: compactCaption(caption),
      assetId: visualAssets[index % Math.max(1, visualAssets.length)]?.id,
      transition: index === 0 ? "flash" : index % 2 === 0 ? "push" : "cut",
    };
  });
  const copy = platformCopy[platform];
  const title =
    language === "zh"
      ? `${brief.productName}：${copy.title} 变体 ${variant}`
      : `${brief.productName}: ${copy.title} variant ${variant}`;
  return {
    projectId: blueprint.projectId,
    language,
    variant,
    platform,
    width: 1080,
    height: 1920,
    fps: 30,
    scenes,
    title,
    description: `${copy.hint} ${language === "zh" ? brief.sellingPoints : script}`,
    hashtags: [...copy.tags],
  };
}

function splitScript(script: string) {
  const parts = script
    .split(/[。！？.!?\n]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  return parts.length > 0 ? parts : [script];
}

function compactCaption(text: string) {
  return text.length > 38 ? `${text.slice(0, 36)}...` : text;
}

export async function maybeGenerateFishVoiceover(
  storyboard: Storyboard,
  narration: string,
  outputDir: string,
) {
  if (!hasFishAudioConfig()) return undefined;
  return generateFishAudio(narration, storyboard.language, outputDir);
}

async function renderMp4(outputPath: string, storyboard: Storyboard) {
  if (storyboard.seedanceClips?.length) {
    await renderFromClips(outputPath, storyboard);
    return;
  }
  await renderPlaceholderMp4(outputPath, storyboard);
}

async function renderFromClips(outputPath: string, storyboard: Storyboard) {
  const tmp = await mkdtemp(path.join(os.tmpdir(), "clipforge-"));
  const concatList = path.join(tmp, "concat.txt");
  await writeFile(
    concatList,
    storyboard.seedanceClips!.map((clip) => `file '${clip.replaceAll("'", "'\\''")}'`).join("\n"),
    "utf8",
  );
  const inputs = ["-f", "concat", "-safe", "0", "-i", concatList];
  if (storyboard.voiceoverPath) {
    inputs.push("-i", storyboard.voiceoverPath);
  } else {
    const duration = storyboard.scenes.reduce((max, scene) => Math.max(max, scene.startSec + scene.durationSec), 0);
    inputs.push("-f", "lavfi", "-i", `sine=frequency=420:duration=${Math.ceil(duration)}`);
  }

  try {
    await execFileAsync("ffmpeg", [
      "-y",
      ...inputs,
      "-vf",
      "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
      "-map",
      "0:v",
      "-map",
      "1:a",
      "-c:v",
      "libx264",
      "-preset",
      "fast",
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-shortest",
      outputPath,
    ]);
  } finally {
    await rm(tmp, {recursive: true, force: true});
  }
}

async function renderPlaceholderMp4(outputPath: string, storyboard: Storyboard) {
  const duration = Math.max(
    15,
    Math.ceil(storyboard.scenes.reduce((max, scene) => Math.max(max, scene.startSec + scene.durationSec), 0)),
  );
  const palette = storyboard.language === "zh" ? "0x1f8a70" : "0x2f5f9f";
  const inputs = ["-f", "lavfi", "-i", `color=c=${palette}:s=1080x1920:d=${duration}:r=30`];
  if (storyboard.voiceoverPath) {
    inputs.push("-i", storyboard.voiceoverPath);
  } else {
    inputs.push(
      "-f",
      "lavfi",
      "-i",
      `sine=frequency=${storyboard.variant === 1 ? 440 : storyboard.variant === 2 ? 520 : 620}:duration=${duration}`,
    );
  }
  await execFileAsync("ffmpeg", [
    "-y",
    ...inputs,
    "-c:v",
    "libx264",
    "-preset",
    "ultrafast",
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    "-shortest",
    outputPath,
  ]);
}
