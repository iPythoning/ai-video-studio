---
name: ai-video-studio
description: "AI Video Studio — Generate + Edit + Export videos. Uses Seedance 2.0 for AI video generation, CapCut Mate for editing (timeline, captions, effects, BGM). One-command scenario-based product promo / short drama via `drama` subcommand (huobao-style 4-layer pipeline: script → characters/scenes → storyboard → render). Trigger: video, 视频, 剪辑, 生成视频, make video, edit video, 短视频, 短剧, 产品推广视频, clip, drama."
metadata:
  openclaw:
    emoji: "🎬"
    category: "creative"
    tags: ["video", "seedance", "capcut", "editing", "ai-generation", "短视频", "短剧", "产品推广"]
    requires:
      bins: ["python3", "curl", "bash"]
      env: ["SEEDANCE_API_KEY", "ANTHROPIC_API_KEY"]
---

# AI Video Studio

AI 视频一站式工作流：Seedance 2.0 生成 + CapCut Mate 剪辑 + 云渲染导出。

## 核心能力

1. **AI 生成视频片段** — 通过文字/图片提示调用 Seedance 2.0 生成 5/8/11 秒视频
2. **自动剪辑合成** — 多片段拼接、字幕叠加、转场效果、BGM
3. **云渲染导出** — 生成最终 MP4

## 一条指令生成场景化视频（NEW — huobao 四层流水线）

`drama` 子命令封装了「剧本 → 角色/场景 → 分镜 → 渲染」完整链路，由 Sonnet 执行 + Opus advisor 自主挑选叙事模板（问题-转折-解决 / 场景蒙太奇 / 故事剧情化 / hybrid）。方法论参考 [`reference/huobao/`](reference/huobao/ATTRIBUTION.md)（CC BY-NC-SA 4.0）。

### 产品推广短视频（一条指令）

```bash
python3 ~/.openclaw/workspace/skills/ai-video-studio/scripts/studio.py drama \
  --mode product \
  --idea "智能保温杯，精英通勤族的一天" \
  --scenario "晨跑/地铁/办公室/加班" \
  --highlights "12 小时保温、航空级不锈钢、一键温控" \
  --shots 6 --duration 5 --ratio 9:16 --lang zh --run
```

### 短剧（一条指令）

```bash
python3 ~/.openclaw/workspace/skills/ai-video-studio/scripts/studio.py drama \
  --mode shortdrama \
  --idea "咖啡厅偶遇前任，一句话揭开三年误会" \
  --shots 6 --duration 8 --ratio 9:16 --lang zh --run
```

### 参数

| 参数 | 说明 |
|------|------|
| `--mode` | `product` 场景化产品推广 / `shortdrama` 短剧 |
| `--idea` | 核心创意或产品一句话描述 |
| `--scenario` | 使用/故事场景约束（可选），advisor 会围绕它构图 |
| `--highlights` | `product` 模式的卖点列表（advisor 会自然融入剧情，不做硬广） |
| `--shots` | 镜头数量，默认 6 |
| `--duration` | 每镜头时长 5/8/11 秒，默认 5 |
| `--ratio` | 画幅，竖屏短视频建议 `9:16` |
| `--advisor-calls` | Opus 咨询次数上限，默认 3 |
| `--run` | 加上则立即执行 Seedance 生成 + ffmpeg 渲染，不加只产出蓝本 JSON |

输出：蓝本 JSON（含 `characters` / `scenes` / `shots` / `narrative_template` / `logline`）保存在 `$MEDIA_DIR/drama-<mode>-<ts>.json`；加 `--run` 后继续走 pipeline 产出最终 mp4。

## 完整工作流（底层）

### 一键生成：从故事板到成品

创建一个 JSON 故事板文件，然后调用 pipeline：

```bash
# 创建故事板
cat > /tmp/storyboard.json << 'EOF'
{
  "title": "产品广告",
  "ratio": "16:9",
  "shots": [
    {"prompt": "A modern smartphone floating in space with golden particles around it, cinematic lighting", "duration": 5, "caption": "全新设计 引领未来"},
    {"prompt": "Hands holding a smartphone with holographic UI elements emerging from screen", "duration": 5, "caption": "触手可及的智能"},
    {"prompt": "Slow motion water splash revealing a smartphone, dramatic lighting", "duration": 5, "caption": "防水新境界"}
  ],
  "bgm_url": null
}
EOF

# 运行完整流程
python3 ~/.openclaw/workspace/skills/ai-video-studio/scripts/studio.py pipeline /tmp/storyboard.json
```

输出：最终视频文件路径（如 `/root/.openclaw/media/studio-xxx.mp4`）

### 故事板字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 项目名称 |
| `ratio` | string | 画面比例: `16:9`, `9:16`, `1:1` |
| `shots[].prompt` | string | Seedance 生成提示词（建议英文，效果更好） |
| `shots[].duration` | int | 每段时长: 5, 8, 11 秒 |
| `shots[].caption` | string | 字幕文字（留空则不加字幕） |
| `shots[].ref_image` | string? | 可选参考图片 URL |
| `bgm_url` | string? | 可选背景音乐 URL |

## 分步使用（灵活组合）

### Step 1: 生成单个视频片段

```bash
python3 ~/.openclaw/workspace/skills/ai-video-studio/scripts/studio.py generate \
  --prompt "一只橘猫在阳光下打哈欠" \
  --ratio 16:9 \
  --duration 5
```

返回：视频文件路径

### Step 2: 合成多个片段

```bash
python3 ~/.openclaw/workspace/skills/ai-video-studio/scripts/studio.py compose \
  --videos /root/.openclaw/media/clip1.mp4,/root/.openclaw/media/clip2.mp4 \
  --captions "第一幕,第二幕" \
  --ratio 16:9
```

返回：草稿 URL + 导出视频路径

### Step 3: 仅用 CapCut Mate 编辑已有视频

```bash
python3 ~/.openclaw/workspace/skills/ai-video-studio/scripts/studio.py compose \
  --videos https://example.com/v1.mp4,https://example.com/v2.mp4 \
  --captions "开头,结尾" \
  --bgm https://example.com/music.mp3 \
  --ratio 9:16
```

## FFmpeg 直出模式（推荐，默认）

pipeline 命令默认使用 ffmpeg 在服务端直出 mp4，不依赖剪映客户端。

### 仅渲染（跳过 Seedance，用已有片段）

```bash
python3 ~/.openclaw/workspace/skills/ai-video-studio/scripts/studio.py render   --videos clip1.mp4,clip2.mp4   --captions "第一幕,第二幕"   --bgm https://example.com/music.mp3   --ratio 16:9 --title myproject
```

返回：最终 mp4 文件路径

### ffmpeg 渲染能力

- 多片段拼接（自动归一化分辨率）
- SRT 字幕烧录（白字黑边，底部居中）
- BGM 混音（原声 100% + BGM 30%）
- H.264 + AAC 编码，秒级渲染

### pipeline 默认 ffmpeg

故事板 JSON 中 renderer 默认 ffmpeg，设 capcut 可切换为剪映草稿模式。

## 注意事项

- Seedance 视频生成通常需要 3-10 分钟/片段，多片段并行提交
- 云渲染需要剪映 API Key（通过 `CAPCUT_API_KEY` 环境变量设置）
- 若无云渲染 Key，仍可生成草稿文件，手动用剪映客户端导出
- 视频输出目录: `/root/.openclaw/media/`
- 推荐中文提示词用于 Seedance，效果更好

## 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `SEEDANCE_API_KEY` | 豆包 Seedance API | 内置 fallback |
| `CAPCUT_MATE_URL` | CapCut Mate 服务地址 | `http://127.0.0.1:30000` |
| `CAPCUT_API_KEY` | 剪映云渲染 Key（可选）| 无 |

