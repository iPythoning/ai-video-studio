import {createWriteStream} from "node:fs";
import {mkdir} from "node:fs/promises";
import path from "node:path";
import {Readable} from "node:stream";
import {pipeline} from "node:stream/promises";
import type {Language, Storyboard} from "../types";

const seedanceEndpoint =
  process.env.SEEDANCE_API_URL ||
  "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks";

export function hasSeedanceConfig() {
  return Boolean(process.env.SEEDANCE_API_KEY || process.env.ARK_API_KEY);
}

export function hasFishAudioConfig() {
  return Boolean(process.env.FISH_AUDIO_API_KEY);
}

export async function generateFishAudio(
  text: string,
  language: Language,
  outputDir: string,
): Promise<string | undefined> {
  const apiKey = process.env.FISH_AUDIO_API_KEY;
  if (!apiKey || !text.trim()) return undefined;

  await mkdir(outputDir, {recursive: true});
  const voiceId =
    language === "zh"
      ? process.env.FISH_AUDIO_VOICE_ZH
      : process.env.FISH_AUDIO_VOICE_EN;
  const response = await fetch("https://api.fish.audio/v1/tts", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      model: process.env.FISH_AUDIO_MODEL || "s2-pro",
    },
    body: JSON.stringify({
      text,
      reference_id: voiceId || undefined,
      format: "mp3",
      sample_rate: 44100,
      mp3_bitrate: 128,
      normalize: true,
      prosody: {
        speed: 1,
        volume: 0,
        normalize_loudness: true,
      },
    }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Fish Audio TTS 失败：${response.status} ${await response.text()}`);
  }

  const audioPath = path.join(outputDir, `${language}-voiceover.mp3`);
  await pipeline(Readable.fromWeb(response.body as unknown as Parameters<typeof Readable.fromWeb>[0]), createWriteStream(audioPath));
  return audioPath;
}

export async function generateSeedanceClips(
  prompts: string[],
  storyboard: Storyboard,
  outputDir: string,
): Promise<string[]> {
  const apiKey = process.env.SEEDANCE_API_KEY || process.env.ARK_API_KEY;
  if (!apiKey) return [];

  await mkdir(outputDir, {recursive: true});
  const duration = nearestSeedanceDuration(
    Math.max(5, Math.round(storyboard.scenes[0]?.durationSec || 5)),
  );
  const selectedPrompts = prompts.slice(0, Number(process.env.SEEDANCE_MAX_CLIPS || 3));
  const clips: string[] = [];

  for (let index = 0; index < selectedPrompts.length; index += 1) {
    const taskId = await submitSeedanceTask(apiKey, selectedPrompts[index], storyboard, duration);
    const videoUrl = await pollSeedanceTask(apiKey, taskId);
    const clipPath = path.join(outputDir, `seedance-${storyboard.language}-${storyboard.platform}-v${storyboard.variant}-${index + 1}.mp4`);
    await downloadFile(videoUrl, clipPath);
    clips.push(clipPath);
  }

  return clips;
}

async function submitSeedanceTask(
  apiKey: string,
  prompt: string,
  storyboard: Storyboard,
  duration: 5 | 8 | 11 | 15,
) {
  const response = await fetch(seedanceEndpoint, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: process.env.SEEDANCE_MODEL || "doubao-seedance-2-0-260128",
      content: [{type: "text", text: prompt}],
      ratio: "9:16",
      duration,
      watermark: false,
      generate_audio: false,
      metadata: {
        project_id: storyboard.projectId,
        language: storyboard.language,
        platform: storyboard.platform,
        variant: storyboard.variant,
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`Seedance 提交失败：${response.status} ${await response.text()}`);
  }
  const data = (await response.json()) as {id?: string; task_id?: string};
  const taskId = data.id || data.task_id;
  if (!taskId) throw new Error(`Seedance 没有返回 task id：${JSON.stringify(data).slice(0, 240)}`);
  return taskId;
}

async function pollSeedanceTask(apiKey: string, taskId: string) {
  const maxWaitSec = Number(process.env.SEEDANCE_MAX_WAIT_SEC || 900);
  const intervalSec = Number(process.env.SEEDANCE_POLL_INTERVAL_SEC || 20);

  for (let elapsed = 0; elapsed <= maxWaitSec; elapsed += intervalSec) {
    if (elapsed > 0) await new Promise((resolve) => setTimeout(resolve, intervalSec * 1000));
    const response = await fetch(`${seedanceEndpoint}/${taskId}`, {
      headers: {Authorization: `Bearer ${apiKey}`},
    });
    if (!response.ok) {
      throw new Error(`Seedance 查询失败：${response.status} ${await response.text()}`);
    }
    const data = (await response.json()) as Record<string, unknown>;
    const status = String(data.status || data.task_status || "unknown");
    if (status === "succeeded" || status === "success" || status === "completed") {
      const url = extractVideoUrl(data);
      if (!url) throw new Error(`Seedance 成功但没有 video url：${JSON.stringify(data).slice(0, 400)}`);
      return url;
    }
    if (status === "failed" || status === "error") {
      throw new Error(`Seedance 生成失败：${JSON.stringify(data).slice(0, 400)}`);
    }
  }
  throw new Error(`Seedance 超时：${taskId}`);
}

function extractVideoUrl(data: Record<string, unknown>) {
  const content = data.content;
  if (Array.isArray(content)) {
    for (const item of content) {
      if (!item || typeof item !== "object") continue;
      const typed = item as Record<string, unknown>;
      const video = typed.video_url;
      if (typeof video === "string") return video;
      if (video && typeof video === "object" && typeof (video as {url?: unknown}).url === "string") {
        return (video as {url: string}).url;
      }
    }
  }
  if (content && typeof content === "object") {
    const video = (content as Record<string, unknown>).video_url;
    if (typeof video === "string") return video;
  }
  if (typeof data.video_url === "string") return data.video_url;
  if (typeof data.url === "string") return data.url;
  return "";
}

async function downloadFile(url: string, outputPath: string) {
  const response = await fetch(url);
  if (!response.ok || !response.body) {
    throw new Error(`下载 Seedance 视频失败：${response.status} ${await response.text()}`);
  }
  await pipeline(Readable.fromWeb(response.body as unknown as Parameters<typeof Readable.fromWeb>[0]), createWriteStream(outputPath));
}

function nearestSeedanceDuration(seconds: number): 5 | 8 | 11 | 15 {
  const allowed = [5, 8, 11, 15] as const;
  return allowed.reduce((best, value) =>
    Math.abs(value - seconds) < Math.abs(best - seconds) ? value : best,
  );
}
