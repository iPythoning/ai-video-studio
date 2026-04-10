# AI Video Studio

**OpenClaw skill** for AI video generation + editing. Generate video clips with [Seedance 2.0](https://www.volcengine.com/product/doubao), edit with [CapCut Mate](https://github.com/Hommy-master/capcut-mate) or FFmpeg, and export — all server-side, no desktop app needed.

## Features

- **AI Video Generation** — Text/image-to-video via ByteDance Seedance 2.0 (Doubao)
- **Smart Editing** — Auto-compose multi-shot storyboards with captions, BGM, and transitions
- **Dual Renderer** — FFmpeg (default, server-side mp4) or CapCut Mate (Jianying draft)
- **OpenClaw Native** — Install as a skill, invoke via natural language through any channel (Telegram, WhatsApp, CLI)

## Quick Start

### As an OpenClaw Skill (recommended)

```bash
# Copy to your OpenClaw workspace
cp -r skills/ai-video-studio ~/.openclaw/workspace/skills/

# Set your Seedance API key
export SEEDANCE_API_KEY="your-key-here"

# Talk to your OpenClaw agent:
# "Generate a 3-shot product video, 16:9, 5 seconds each, with captions"
```

### Standalone CLI

```bash
# Generate a single clip
python3 scripts/studio.py generate \
  --prompt "A cat yawning in golden sunlight" \
  --ratio 16:9 --duration 5

# Render existing clips into final video (FFmpeg)
python3 scripts/studio.py render \
  --videos clip1.mp4,clip2.mp4 \
  --captions "Scene 1,Scene 2" \
  --bgm https://example.com/music.mp3 \
  --ratio 16:9

# Full pipeline from storyboard
python3 scripts/studio.py pipeline storyboard.json
```

### Storyboard Format

```json
{
  "title": "Product Ad",
  "ratio": "16:9",
  "renderer": "ffmpeg",
  "shots": [
    {
      "prompt": "Modern smartphone floating in space with golden particles",
      "duration": 5,
      "caption": "Next-Gen Design"
    },
    {
      "prompt": "Hands holding smartphone with holographic UI elements",
      "duration": 5,
      "caption": "Intelligence at Your Fingertips"
    }
  ],
  "bgm_url": null
}
```

## Architecture

```
User Intent
    │
    ▼
┌─────────────┐    ┌──────────────┐
│  Seedance    │───▶│  Video Clips │
│  2.0 API     │    │  (.mp4 × N)  │
└─────────────┘    └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │   Renderer   │
                   │              │
                   │ ┌──────────┐ │
                   │ │  FFmpeg  │ │ ← Default: concat + subtitle burn + BGM mix
                   │ └──────────┘ │
                   │ ┌──────────┐ │
                   │ │ CapCut   │ │ ← Optional: Jianying draft with effects
                   │ │  Mate    │ │
                   │ └──────────┘ │
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │  Final MP4   │
                   └──────────────┘
```

## Commands

| Command | Description | Dependencies |
|---------|-------------|-------------|
| `generate` | Generate a single clip via Seedance 2.0 | Seedance API key |
| `compose` | Create Jianying draft via CapCut Mate | capcut-mate service |
| `render` | FFmpeg direct render (concat + subs + BGM) | ffmpeg |
| `pipeline` | End-to-end from storyboard JSON | Seedance + ffmpeg |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `SEEDANCE_API_KEY` | Doubao Seedance API key | Built-in fallback |
| `CAPCUT_MATE_URL` | CapCut Mate service URL | `http://127.0.0.1:30000` |
| `CAPCUT_API_KEY` | Jianying cloud render key (optional) | — |
| `MEDIA_DIR` | Output directory | `/root/.openclaw/media` |

## Prerequisites

- Python 3.11+
- `ffmpeg` (for render mode)
- `requests` + `pyyaml` (pip)
- [CapCut Mate](https://github.com/Hommy-master/capcut-mate) (optional, for compose mode)
- [Seedance 2.0 API access](https://www.volcengine.com/product/doubao) (for generate/pipeline)

## FFmpeg Render Capabilities

- Multi-clip concatenation with automatic resolution normalization
- SRT subtitle burn-in (white text, black outline, bottom-center)
- BGM mixing (original audio 100% + BGM 30%)
- H.264 + AAC encoding, fast preset
- Sub-second render time for short videos

## License

MIT — see [LICENSE](LICENSE).

## Built With

- [OpenClaw](https://openclaw.ai) — AI agent framework
- [Seedance 2.0](https://www.volcengine.com/product/doubao) — ByteDance video generation
- [CapCut Mate](https://github.com/Hommy-master/capcut-mate) — Open-source Jianying automation
- [FFmpeg](https://ffmpeg.org) — Video processing
