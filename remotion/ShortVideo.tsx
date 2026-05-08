import {AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {Storyboard} from "@/lib/types";

export const defaultStoryboard: Storyboard = {
  projectId: "demo",
  language: "zh",
  variant: 1,
  platform: "tiktok",
  width: 1080,
  height: 1920,
  fps: 30,
  title: "ClipForge Local",
  description: "本地优先的短视频生成模板",
  hashtags: ["#Shorts"],
  scenes: [
    {
      id: "s1",
      startSec: 0,
      durationSec: 4,
      narration: "上传素材",
      caption: "上传素材",
      transition: "flash",
    },
    {
      id: "s2",
      startSec: 4,
      durationSec: 4,
      narration: "分析对标风格",
      caption: "分析对标风格",
      transition: "push",
    },
    {
      id: "s3",
      startSec: 8,
      durationSec: 4,
      narration: "生成多语言变体",
      caption: "生成多语言变体",
      transition: "cut",
    },
    {
      id: "s4",
      startSec: 12,
      durationSec: 4,
      narration: "批量导出",
      caption: "批量导出",
      transition: "flash",
    },
  ],
};

export type ShortVideoProps = {
  storyboard: Storyboard;
};

export function ShortVideo({storyboard}: ShortVideoProps) {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{background: "#14120f", fontFamily: "Inter, Arial, sans-serif"}}>
      {storyboard.scenes.map((scene, index) => (
        <Sequence
          key={scene.id}
          from={Math.round(scene.startSec * fps)}
          durationInFrames={Math.round(scene.durationSec * fps)}
          premountFor={fps}
        >
          <Scene caption={scene.caption} index={index} title={storyboard.title} />
        </Sequence>
      ))}
      <SafeZone />
    </AbsoluteFill>
  );
}

function Scene({caption, index, title}: {caption: string; index: number; title: string}) {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 12], [0, 1], {extrapolateRight: "clamp"});
  const y = interpolate(frame, [0, 18], [70, 0], {extrapolateRight: "clamp"});
  const colors = ["#1f8a70", "#e0563f", "#2f5f9f", "#f4d35e"];
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        padding: 96,
        background: colors[index % colors.length],
      }}
    >
      <div style={{opacity, transform: `translateY(${y}px)`}}>
        <div
          style={{
            display: "inline-block",
            border: "6px solid #14120f",
            background: "#fffaf1",
            color: "#14120f",
            padding: "16px 28px",
            fontSize: 42,
            fontWeight: 900,
            marginBottom: 42,
          }}
        >
          {title}
        </div>
        <div
          style={{
            color: "white",
            fontSize: 92,
            fontWeight: 950,
            lineHeight: 1,
            textShadow: "0 8px 0 rgba(20,18,15,0.65)",
            wordBreak: "break-word",
          }}
        >
          {caption}
        </div>
      </div>
    </AbsoluteFill>
  );
}

function SafeZone() {
  return (
    <AbsoluteFill style={{pointerEvents: "none"}}>
      <div
        style={{
          position: "absolute",
          top: 180,
          right: 160,
          bottom: 360,
          left: 80,
          border: "3px dashed rgba(255,255,255,0.35)",
        }}
      />
    </AbsoluteFill>
  );
}
