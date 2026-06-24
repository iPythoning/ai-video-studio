# AI Video Studio

**OpenClaw skill** for AI video generation + editing. Generate video clips with [Seedance 2.0](https://www.volcengine.com/product/doubao), edit with [CapCut Mate](https://github.com/Hommy-master/capcut-mate) or FFmpeg, and export — all server-side, no desktop app needed.

## Features

- **AI Video Generation** — Text/image-to-video via ByteDance Seedance 2.0 (Doubao)
- **Smart Editing** — Auto-compose multi-shot storyboards with captions, BGM, and transitions
- **Multi Renderer** — FFmpeg (default MP4), CapCut Mate, local CapCut/Jianying draft manifests
- **Draft Backends** — Storyboards with real-shot assets can become CapCut/Jianying draft plans for later pyCapCut / pyJianYingDraft execution
- **Social Reply Queue** — Normalize comments from Douyin/TikTok/Instagram/YouTube exports into a deduped SQLite review queue with safe draft replies
- **One-command Drama / Product Promo** — `drama` subcommand runs a four-layer pipeline (script → characters/scenes → storyboard → render) with autonomous narrative-template selection; methodology ported from [huobao-drama](https://github.com/chatfire-AI/huobao-drama) (CC BY-NC-SA 4.0, see `skills/ai-video-studio/reference/huobao/ATTRIBUTION.md`)
- **OpenClaw Native** — Install as a skill, invoke via natural language through any channel (Telegram, WhatsApp, CLI)

## One-command Scenario Video

```bash
# Scenario-based product promotion
python3 scripts/studio.py drama \
  --mode product \
  --idea "Smart thermos for commuters" \
  --scenario "morning run / subway / office" \
  --highlights "12h heat retention, aerospace steel" \
  --shots 6 --duration 5 --ratio 9:16 --lang en --run

# Short drama
python3 scripts/studio.py drama \
  --mode shortdrama \
  --idea "Café reunion: one sentence uncovers a three-year misunderstanding" \
  --shots 6 --duration 8 --ratio 9:16 --lang zh --run
```

Requires `ANTHROPIC_API_KEY` (Sonnet executor + Opus advisor) in addition to `SEEDANCE_API_KEY`.

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

# Create local CapCut/Jianying draft manifests from storyboard assets
python3 scripts/studio.py draft storyboard.json --backend capcut --draft-root "/path/to/CapCut Drafts"
python3 scripts/studio.py draft storyboard.json --backend jianying --draft-root "/path/to/JianyingPro Drafts"

# Create 3 variants × zh/en local draft manifests from a product brief and real-shot assets
python3 scripts/studio.py template-draft brief.json \
  --assets "/path/to/demo1.mp4,/path/to/demo2.mp4" \
  --backend capcut --draft-root "/path/to/CapCut Drafts" \
  --template ugc_hook_cta --locales zh,en --variants 3

# Turn social comment exports into reviewable reply jobs
python3 scripts/social_replies.py comments.json --db social.sqlite --brand ClipForge --url https://example.com/buy
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

For real-shot material entering the local draft backend, put a local asset path on each shot:

```json
{
  "title": "UGC Product Demo",
  "ratio": "9:16",
  "renderer": "capcut_draft",
  "draft_root": "/path/to/CapCut Drafts",
  "lang": "zh",
  "shots": [
    {
      "asset": "/absolute/path/to/real-shoot-01.mp4",
      "duration": 5,
      "caption": "三秒看懂",
      "voiceover": "/absolute/path/to/voice.zh.mp3"
    }
  ],
  "locales": {
    "en": {
      "shots": [{"caption": "Get it in 3 sec"}]
    }
  }
}
```

This writes one draft-plan JSON per locale. The next execution layer can map those operations to `pycapcut` or `pyJianYingDraft`.

### Multilingual Template Drafts

`scripts/draft_templates.py` turns a product brief plus real-shot assets into reusable CapCut/Jianying draft packages. The first built-in template is `ugc_hook_cta`:

- 3 slots: hook, benefit, CTA
- 9:16 default canvas and lower-third-safe captions
- `variants` controls how many creative cuts are produced
- `locales` controls language manifests, for example `zh,en`
- no Seedance, no Anthropic, no TTS required; it uses existing local assets

Example brief:

```json
{
  "product_name": "智能保温杯",
  "brand_name": "ClipForge",
  "audience": "通勤族",
  "selling_points": ["12小时保温", "一键开盖"],
  "cta": "现在领取试用",
  "slug": "mug-campaign"
}
```

The HTTP service exposes the same local-first template flow at `POST /draft/template`:

```json
{
  "brief": {
    "product_name": "智能保温杯",
    "brand_name": "ClipForge",
    "audience": "通勤族",
    "selling_points": ["12小时保温"],
    "cta": "现在领取试用",
    "slug": "mug-campaign"
  },
  "assets": ["/path/to/demo.mp4"],
  "backend": "capcut",
  "template_id": "ugc_hook_cta",
  "locales": ["zh", "en"],
  "variants": 3
}
```

### Social Comment Reply Queue

`scripts/social_replies.py` is the safe core for the "all social media auto-reply" product line. It does not log in or send replies by itself. It:

- accepts comment exports from Douyin/TikTok/Instagram/YouTube-style JSON fields
- normalizes `platform`, `comment_id`, `post_id`, `author`, `text`, and `created_at`
- dedupes comments in SQLite by `(platform, comment_id)`
- drafts replies into `pending_review`
- routes refund, complaint, scam, legal, and similar terms to `needs_human`

Later platform adapters can plug into this queue as `CommentProvider` and `ReplySender` layers, including the TzFilm-style "export comments → plan replies → controlled browser send" pattern.

The HTTP service exposes the same safe planning layer at `POST /social/replies/plan`:

```json
{
  "comments": [
    {
      "platform": "youtube",
      "comment_id": "yt-1",
      "video_id": "short-1",
      "author": "lee",
      "text": "How much is this?"
    }
  ],
  "db_path": "social.sqlite",
  "brand_name": "ClipForge",
  "product_url": "https://example.com/buy"
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
| `template-draft` | Product brief + local assets → multilingual draft manifests | stdlib + draft backend |
| `social_replies.py` | Turn comment exports into reviewable reply jobs | stdlib SQLite |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `SEEDANCE_API_KEY` | Doubao Seedance API key | Built-in fallback |
| `CAPCUT_MATE_URL` | CapCut Mate service URL | `http://127.0.0.1:30000` |
| `CAPCUT_API_KEY` | Jianying cloud render key (optional) | — |
| `CAPCUT_DRAFT_ROOT` | Local CapCut draft folder for `capcut_draft` | — |
| `JIANYING_DRAFT_ROOT` | Local Jianying draft folder for `jianying_draft` | — |
| `MEDIA_DIR` | Output directory | `/root/.openclaw/media` |

## Prerequisites

- Python 3.11+
- `ffmpeg` (for render mode)
- `requests` + `pyyaml` (pip)
- [CapCut Mate](https://github.com/Hommy-master/capcut-mate) (optional, for compose mode)
- [pyCapCut](https://github.com/GuanYixuan/pyCapCut) and [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft) are the target local draft execution libraries. Current integration writes normalized draft manifests first, then maps to these libraries in the executor layer.
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
