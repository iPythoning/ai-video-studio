#!/usr/bin/env python3
"""
AI Video Studio — Seedance generation + CapCut Mate editing pipeline.

Subcommands:
    generate   — Generate a single video clip via Seedance 2.0
    compose    — Compose multiple clips into a final video via CapCut Mate
    pipeline   — End-to-end from storyboard JSON
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# ─── Config ────────────────────────────────────────────────────────────────
SEEDANCE_KEY = os.environ.get("SEEDANCE_API_KEY", "")
SEEDANCE_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
CAPCUT_URL = os.environ.get("CAPCUT_MATE_URL", "http://127.0.0.1:30000")
CAPCUT_API_KEY = os.environ.get("CAPCUT_API_KEY")
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", "/root/.openclaw/media"))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

API = lambda ep: f"{CAPCUT_URL}/openapi/capcut-mate/v1/{ep}"


def log(msg):
    print(f"[studio] {msg}", flush=True)


# ─── Seedance ──────────────────────────────────────────────────────────────
def seedance_submit(prompt, ratio="16:9", duration=5, ref_image=None):
    content = [{"type": "text", "text": prompt}]
    if ref_image:
        content.append({"type": "image_url", "image_url": {"url": ref_image}, "role": "reference_image"})
    body = {
        "model": "doubao-seedance-2-0-260128",
        "content": content,
        "ratio": ratio,
        "duration": duration,
        "watermark": False,
        "generate_audio": True,
    }
    r = requests.post(SEEDANCE_URL, json=body,
                      headers={"Authorization": f"Bearer {SEEDANCE_KEY}",
                               "Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    task_id = r.json().get("id")
    if not task_id:
        raise RuntimeError(f"Seedance submit failed: {r.text}")
    return task_id


def seedance_poll(task_id, max_wait=900, interval=20):
    log(f"Polling {task_id}...")
    headers = {"Authorization": f"Bearer {SEEDANCE_KEY}"}
    for _ in range(max_wait // interval):
        time.sleep(interval)
        r = requests.get(f"{SEEDANCE_URL}/{task_id}", headers=headers, timeout=30)
        data = r.json()
        status = data.get("status", "unknown")
        log(f"  {task_id}: {status}")
        if status == "succeeded":
            for c in data.get("content", []):
                if isinstance(c, dict) and c.get("type") == "video_url":
                    return c["video_url"]["url"]
            # Try alternate response format
            content = data.get("content", {})
            if isinstance(content, dict) and "video_url" in content:
                return content["video_url"]
            raise RuntimeError(f"Succeeded but no video URL: {json.dumps(data)[:300]}")
        if status == "failed":
            raise RuntimeError(f"Seedance failed: {json.dumps(data)[:300]}")
    raise TimeoutError(f"Seedance timeout after {max_wait}s: {task_id}")


def seedance_download(video_url, tag="clip"):
    outpath = MEDIA_DIR / f"seedance-{tag}-{int(time.time())}.mp4"
    r = requests.get(video_url, stream=True, timeout=120)
    r.raise_for_status()
    with open(outpath, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    log(f"Downloaded: {outpath} ({outpath.stat().st_size // 1024}KB)")
    return str(outpath)


def generate_clip(prompt, ratio="16:9", duration=5, ref_image=None, tag="clip"):
    task_id = seedance_submit(prompt, ratio, duration, ref_image)
    log(f"Submitted: {task_id} — \"{prompt[:40]}...\"")
    video_url = seedance_poll(task_id)
    return seedance_download(video_url, tag)


# ─── CapCut Mate ───────────────────────────────────────────────────────────
def capcut_post(endpoint, payload):
    r = requests.post(API(endpoint), json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("code") not in (None, 0, 200, "200"):
        raise RuntimeError(f"CapCut {endpoint} error: {json.dumps(data)[:300]}")
    return data


def compose_video(video_paths, captions=None, ratio="16:9", bgm_url=None, clip_durations=None):
    """Create a CapCut draft from video clips, add captions, optionally render."""
    US = 1_000_000  # 1 second in microseconds (capcut-mate uses μs)
    dims = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}
    w, h = dims.get(ratio, (1920, 1080))
    durations_s = clip_durations or [5.0] * len(video_paths)

    # 1. Create draft
    log("Creating draft...")
    draft = capcut_post("create_draft", {"width": w, "height": h})
    draft_url = draft.get("draft_url", "")
    if not draft_url:
        raise RuntimeError(f"No draft_url: {json.dumps(draft)[:300]}")
    log(f"Draft: {draft_url}")

    # 2. Build timelines manually (μs units)
    timelines = []
    offset = 0
    for dur in durations_s:
        dur_us = int(dur * US)
        timelines.append({"start": offset, "end": offset + dur_us})
        offset += dur_us

    # 3. Build video_infos via API
    video_urls = []
    for p in video_paths:
        video_urls.append(p if p.startswith("http") else f"file://{p}")
    vi_resp = capcut_post("video_infos", {"video_urls": video_urls, "timelines": timelines, "width": w, "height": h})
    video_infos_str = vi_resp.get("infos") or json.dumps(vi_resp.get("data", {}).get("infos", []))

    # 4. Add videos
    log(f"Adding {len(video_paths)} video clips...")
    capcut_post("add_videos", {"draft_url": draft_url, "video_infos": video_infos_str})

    # 5. Add captions
    if captions:
        texts = [t for t in captions if t]
        if texts:
            cap_tl = [timelines[i] for i, t in enumerate(captions) if t and i < len(timelines)]
            ci_resp = capcut_post("caption_infos", {"texts": texts, "timelines": cap_tl})
            cap_infos = ci_resp.get("infos") or json.dumps(ci_resp.get("data", {}).get("infos", []))
            log(f"Adding {len(texts)} captions...")
            capcut_post("add_captions", {"draft_url": draft_url, "captions": cap_infos})

    # 6. Add BGM
    if bgm_url:
        total_us = offset
        log("Adding BGM...")
        audio_info = [{"url": bgm_url, "start": 0, "duration": total_us, "volume": 0.5}]
        capcut_post("add_audios", {"draft_url": draft_url, "audio_infos": json.dumps(audio_info)})

    # 7. Save draft
    log("Saving draft...")
    capcut_post("save_draft", {"draft_url": draft_url})

    # 8. Try cloud render (optional)
    result = {"draft_url": draft_url, "video_path": None}
    if CAPCUT_API_KEY:
        log("Submitting cloud render...")
        gen = capcut_post("gen_video", {"draft_url": draft_url, "apiKey": CAPCUT_API_KEY})
        task_id = gen.get("data", {}).get("task_id") or gen.get("task_id")
        if task_id:
            for _ in range(60):
                time.sleep(10)
                st = capcut_post("gen_video_status", {"task_id": task_id})
                status = st.get("data", {}).get("status") or st.get("status")
                log(f"  Render: {status}")
                if status in ("success", "completed", "succeeded"):
                    video_url = st.get("data", {}).get("video_url") or st.get("video_url")
                    if video_url:
                        outpath = MEDIA_DIR / f"studio-{int(time.time())}.mp4"
                        r = requests.get(video_url, stream=True, timeout=120)
                        with open(outpath, "wb") as f:
                            for chunk in r.iter_content(8192):
                                f.write(chunk)
                        result["video_path"] = str(outpath)
                        log(f"Final video: {outpath}")
                    break
                if status in ("failed", "error"):
                    log(f"Render failed: {json.dumps(st)[:200]}")
                    break
    else:
        log("No CAPCUT_API_KEY — draft saved but not rendered. Open in Jianying to export.")

    return result


# ─── Pipeline ──────────────────────────────────────────────────────────────
def run_pipeline(storyboard_path):
    sb = json.loads(Path(storyboard_path).read_text())
    title = sb.get("title", "untitled")
    ratio = sb.get("ratio", "16:9")
    shots = sb.get("shots", [])
    bgm_url = sb.get("bgm_url")

    log(f"Pipeline: '{title}' — {len(shots)} shots, ratio={ratio}")

    # Phase 1: Generate all clips in parallel
    clip_paths = [None] * len(shots)
    log("Phase 1: Submitting Seedance tasks...")

    task_ids = []
    for i, shot in enumerate(shots):
        tid = seedance_submit(shot["prompt"], ratio, shot.get("duration", 5), shot.get("ref_image"))
        task_ids.append((i, tid, shot["prompt"]))
        log(f"  Shot {i+1}: {tid} — \"{shot['prompt'][:40]}...\"")

    log("Phase 1: Polling all tasks...")
    with ThreadPoolExecutor(max_workers=min(len(task_ids), 4)) as pool:
        futures = {}
        for i, tid, prompt in task_ids:
            f = pool.submit(seedance_poll, tid)
            futures[f] = (i, tid)
        for f in as_completed(futures):
            i, tid = futures[f]
            try:
                video_url = f.result()
                clip_paths[i] = seedance_download(video_url, f"shot{i+1}")
            except Exception as e:
                log(f"  Shot {i+1} FAILED: {e}")

    ok_clips = [(i, p) for i, p in enumerate(clip_paths) if p]
    if not ok_clips:
        log("All shots failed. Aborting.")
        return None

    log(f"Phase 1 done: {len(ok_clips)}/{len(shots)} clips ready")

    # Phase 2: Compose via CapCut Mate
    log("Phase 2: Composing...")
    captions = [shots[i].get("caption", "") for i, _ in ok_clips]
    paths = [p for _, p in ok_clips]
    renderer = sb.get("renderer", "ffmpeg")
    if renderer == "ffmpeg":
        clip_durs = [s.get("duration", 5) for i, s in enumerate(shots) if clip_paths[i]]
        outpath = ffmpeg_render(paths, captions, ratio, bgm_url,
                                clip_durations=clip_durs, title=title.replace(" ", "_"))
        result = {"video_path": outpath, "renderer": "ffmpeg"}
    else:
        result = compose_video(paths, captions, ratio, bgm_url,
                               clip_durations=[s.get("duration", 5) for i, s in enumerate(shots) if clip_paths[i]])

    if result.get("video_path"):
        log(f"Final video: {result['video_path']}")
    elif result.get("draft_url"):
        log(f"Draft: {result['draft_url']} — open in Jianying to export")

    return result


# ─── FFmpeg 渲染（服务端直出 mp4，不依赖剪映） ──────────────────────────────
import subprocess
import shutil
import tempfile


def _srt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ffmpeg_render(video_paths, captions=None, ratio="16:9", bgm_url=None,
                  clip_durations=None, title="output"):
    """Concatenate clips + burn subtitles + mix BGM using ffmpeg. No external deps."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    tmpdir = tempfile.mkdtemp(prefix="studio-")
    durations = clip_durations or [5.0] * len(video_paths)
    dims = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}
    w, h = dims.get(ratio, (1920, 1080))
    ts = int(time.time())

    # 1. Download remote videos to local temp files
    local_clips = []
    for i, p in enumerate(video_paths):
        if p.startswith("http"):
            local = os.path.join(tmpdir, f"clip{i}.mp4")
            log(f"Downloading clip {i+1}...")
            r = requests.get(p, stream=True, timeout=120)
            r.raise_for_status()
            with open(local, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            local_clips.append(local)
        else:
            local_clips.append(p)

    # 2. Normalize each clip to same resolution + codec
    normalized = []
    for i, clip in enumerate(local_clips):
        norm = os.path.join(tmpdir, f"norm{i}.mp4")
        dur_arg = str(durations[i]) if i < len(durations) else "5"
        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                   f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", "-t", dur_arg, norm,
        ]
        log(f"Normalizing clip {i+1}/{len(local_clips)}...")
        subprocess.run(cmd, capture_output=True, check=True)
        normalized.append(norm)

    # 3. Generate SRT subtitle file
    srt_path = None
    if captions:
        srt_path = os.path.join(tmpdir, "subs.srt")
        offset = 0.0
        with open(srt_path, "w", encoding="utf-8") as f:
            idx = 1
            for i, text in enumerate(captions):
                dur = durations[i] if i < len(durations) else 5.0
                if not text:
                    offset += dur
                    continue
                f.write(f"{idx}\n")
                f.write(f"{_srt_ts(offset)} --> {_srt_ts(offset + dur)}\n")
                f.write(f"{text}\n\n")
                idx += 1
                offset += dur

    # 4. Concat list file
    concat_list = os.path.join(tmpdir, "concat.txt")
    with open(concat_list, "w") as f:
        for n in normalized:
            f.write(f"file '{n}'\n")

    # 5. Build ffmpeg command
    outpath = str(MEDIA_DIR / f"studio-{title}-{ts}.mp4")
    total_dur = sum(durations)

    # Download BGM if provided
    bgm_local = None
    if bgm_url:
        bgm_local = os.path.join(tmpdir, "bgm.mp3")
        log("Downloading BGM...")
        r = requests.get(bgm_url, stream=True, timeout=60)
        r.raise_for_status()
        with open(bgm_local, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

    # Subtitle filter string
    sub_filter = ""
    if srt_path:
        esc = srt_path.replace("\\", "\\\\").replace(":", "\\:")
        sub_filter = (
            f"subtitles='{esc}':force_style="
            f"'FontSize=24,PrimaryColour=&Hffffff&,"
            f"OutlineColour=&H000000&,Outline=2,Alignment=2,MarginV=40'"
        )

    if bgm_local and sub_filter:
        # Both subtitles + BGM
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-i", bgm_local,
            "-filter_complex",
            f"[0:v]{sub_filter}[vout];"
            f"[0:a]volume=1.0[orig];"
            f"[1:a]volume=0.3,atrim=0:{total_dur},apad[bgm];"
            f"[orig][bgm]amix=inputs=2:duration=shortest[aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-movflags", "+faststart", outpath,
        ]
    elif bgm_local:
        # BGM only, no subtitles
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-i", bgm_local,
            "-filter_complex",
            f"[0:a]volume=1.0[orig];"
            f"[1:a]volume=0.3,atrim=0:{total_dur},apad[bgm];"
            f"[orig][bgm]amix=inputs=2:duration=shortest[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-movflags", "+faststart", outpath,
        ]
    elif sub_filter:
        # Subtitles only, no BGM
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-vf", sub_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac",
            "-movflags", "+faststart", outpath,
        ]
    else:
        # Plain concat
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac",
            "-movflags", "+faststart", outpath,
        ]

    log("Rendering final video...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"ffmpeg error: {result.stderr[-500:]}")
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode})")

    size = os.path.getsize(outpath)
    log(f"Done! {outpath} ({size // 1024}KB)")

    shutil.rmtree(tmpdir, ignore_errors=True)
    return outpath


# ─── CLI ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AI Video Studio")
    sub = parser.add_subparsers(dest="cmd")

    # generate
    gen = sub.add_parser("generate", help="Generate a single clip via Seedance")
    gen.add_argument("--prompt", required=True)
    gen.add_argument("--ratio", default="16:9")
    gen.add_argument("--duration", type=int, default=5, choices=[5, 8, 11])
    gen.add_argument("--ref-image", default=None)

    # compose
    comp = sub.add_parser("compose", help="Compose clips via CapCut Mate")
    comp.add_argument("--videos", required=True, help="Comma-separated video paths/URLs")
    comp.add_argument("--captions", default=None, help="Comma-separated captions")
    comp.add_argument("--ratio", default="16:9")
    comp.add_argument("--bgm", default=None, help="BGM audio URL")

    # pipeline
    pipe = sub.add_parser("pipeline", help="End-to-end from storyboard JSON")
    pipe.add_argument("storyboard", help="Path to storyboard JSON file")

    # render (ffmpeg only, from existing clips)
    rend = sub.add_parser("render", help="FFmpeg render: concat clips + subtitles + BGM → mp4")
    rend.add_argument("--videos", required=True, help="Comma-separated video paths/URLs")
    rend.add_argument("--captions", default=None, help="Comma-separated captions")
    rend.add_argument("--ratio", default="16:9")
    rend.add_argument("--bgm", default=None, help="BGM audio URL")
    rend.add_argument("--title", default="output", help="Output filename tag")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    if args.cmd == "generate":
        path = generate_clip(args.prompt, args.ratio, args.duration, args.ref_image)
        print(path)

    elif args.cmd == "compose":
        videos = [v.strip() for v in args.videos.split(",")]
        captions = [c.strip() for c in args.captions.split(",")] if args.captions else None
        result = compose_video(videos, captions, args.ratio, args.bgm)
        print(json.dumps(result, indent=2))

    elif args.cmd == "render":
        videos = [v.strip() for v in args.videos.split(",")]
        captions = [c.strip() for c in args.captions.split(",")] if args.captions else None
        outpath = ffmpeg_render(videos, captions, args.ratio, args.bgm, title=args.title)
        print(outpath)

    elif args.cmd == "pipeline":
        result = run_pipeline(args.storyboard)
        if result:
            print(json.dumps(result, indent=2))
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()