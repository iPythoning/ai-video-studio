import {execFile} from "node:child_process";
import {promisify} from "node:util";
import type {AssetItem} from "./types";

const execFileAsync = promisify(execFile);

export function inferAssetKind(fileName: string, mimeType: string, isReference = false): AssetItem["kind"] {
  if (isReference) return "reference";
  if (mimeType.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(fileName)) return "image";
  if (mimeType.startsWith("video/") || /\.(mp4|mov|webm|m4v)$/i.test(fileName)) return "video";
  if (mimeType.startsWith("audio/") || /\.(mp3|wav|m4a|aac)$/i.test(fileName)) return "audio";
  return "unknown";
}

export async function probeAsset(asset: AssetItem): Promise<AssetItem> {
  if (!["video", "audio", "reference", "image"].includes(asset.kind)) return asset;
  try {
    const {stdout} = await execFileAsync("ffprobe", [
      "-v",
      "error",
      "-print_format",
      "json",
      "-show_format",
      "-show_streams",
      asset.path,
    ]);
    const info = JSON.parse(stdout) as {
      format?: {duration?: string};
      streams?: Array<{codec_type?: string; width?: number; height?: number}>;
    };
    const video = info.streams?.find((stream) => stream.codec_type === "video");
    return {
      ...asset,
      durationSec: info.format?.duration ? Math.round(Number(info.format.duration)) : undefined,
      width: video?.width,
      height: video?.height,
    };
  } catch {
    return {...asset, status: asset.kind === "unknown" ? "needs-review" : "ready"};
  }
}

export function sanitizeFileName(name: string) {
  return name.replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/-+/g, "-").slice(0, 100);
}
