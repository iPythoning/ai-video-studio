import test from "node:test";
import assert from "node:assert/strict";
import {buildStoryboard, localAdapters} from "../lib/adapters/local";
import {storyboardToSrt} from "../lib/srt";
import type {AssetManifest, ProjectBrief} from "../lib/types";

const brief: ProjectBrief = {
  productName: "ClipForge",
  targetAudience: "跨境营销团队",
  sellingPoints: "省时间，批量生成多语言社媒短视频",
  tone: "直接可信",
  sourceScript: "省时间。自动生成短视频。现在开始测试。",
  forbiddenWords: [],
  targetPlatforms: ["tiktok", "reels", "shorts"],
};

test("对标视频生成稳定 StyleBlueprint", async () => {
  const manifest: AssetManifest = {
    projectId: "p1",
    createdAt: "2026-05-07T00:00:00.000Z",
    referenceAssetId: "r1",
    assets: [
      {
        id: "r1",
        kind: "reference",
        fileName: "ref.mp4",
        path: "/tmp/ref.mp4",
        mimeType: "video/mp4",
        sizeBytes: 1000,
        durationSec: 19,
        width: 1080,
        height: 1920,
        status: "ready",
      },
    ],
  };
  const blueprint = await localAdapters.visualAnalyze(manifest);
  assert.equal(blueprint.source, "reference-video");
  assert.equal(blueprint.targetDurationSec, 19);
  assert.equal(blueprint.captionPosition, "center-safe");
  assert.ok(blueprint.safeZone.bottomPx >= 300);
});

test("分镜输出符合 9:16 双语社媒结构", async () => {
  const blueprint = await localAdapters.visualAnalyze({
    projectId: "p2",
    createdAt: "2026-05-07T00:00:00.000Z",
    assets: [],
  });
  const script = await localAdapters.scriptRewrite(brief, "en", 2);
  const storyboard = buildStoryboard(brief, blueprint, script, "en", "shorts", 2, []);
  assert.equal(storyboard.width, 1080);
  assert.equal(storyboard.height, 1920);
  assert.equal(storyboard.language, "en");
  assert.equal(storyboard.scenes.length, blueprint.sceneCount);
  assert.ok(storyboard.scenes[0].durationSec > 0);
  assert.match(storyboard.description, /search|Title|Turn|ClipForge/i);
});

test("SRT 字幕包含递增时间轴", () => {
  const storyboard = buildStoryboard(
    brief,
    {
      projectId: "p3",
      source: "default-local",
      targetDurationSec: 16,
      hookType: "problem",
      sceneCount: 4,
      avgShotLengthSec: 4,
      captionPosition: "center-safe",
      captionEmphasis: "keyword-pop",
      bRollDensity: "medium",
      audioMix: {voiceDb: -3, musicDb: -18},
      ctaAtSec: 12,
      safeZone: {topPx: 180, rightPx: 160, bottomPx: 360, leftPx: 80},
    },
    brief.sourceScript,
    "zh",
    "tiktok",
    1,
    [],
  );
  const srt = storyboardToSrt(storyboard);
  assert.match(srt, /00:00:00,000 --> 00:00:03,750/);
  assert.match(srt, /00:00:11,250 --> 00:00:15,000/);
});
