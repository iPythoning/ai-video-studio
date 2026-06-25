"""Draft backend planning for Jianying / CapCut.

This module keeps the product pipeline independent from a specific editor
library. It converts our storyboard into a normalized operation list that can
be executed by pyJianYingDraft, pyCapCut, or inspected in tests.
"""
from __future__ import annotations

import json
import importlib
from pathlib import Path
from typing import Any, Literal

Backend = Literal["jianying", "capcut"]


def build_draft_plan(
    storyboard: dict[str, Any],
    *,
    backend: Backend,
    draft_root: str,
    draft_name: str | None = None,
) -> dict[str, Any]:
    """Build a backend-neutral draft operation plan from a storyboard."""
    if backend not in {"jianying", "capcut"}:
        raise ValueError(f"unsupported draft backend: {backend}")

    title = draft_name or _safe_name(storyboard.get("title") or "ai-video")
    ratio = storyboard.get("ratio", "9:16")
    canvas = _canvas_for_ratio(ratio)
    lang = storyboard.get("lang", "zh")
    platform = storyboard.get("platform", "")
    localized = storyboard.get("locales") or {}
    source_locales = [lang, *[key for key in localized.keys() if key != lang]]

    operations: list[dict[str, Any]] = [
        {
            "op": "create_draft",
            "backend": backend,
            "draft_root": str(Path(draft_root)),
            "draft_name": title,
            "canvas": canvas,
            "template": storyboard.get("template") or {},
            "platform": platform,
        }
    ]

    offset = 0.0
    for index, shot in enumerate(storyboard.get("shots") or []):
        duration = float(shot.get("duration") or 5)
        asset = _shot_asset(shot)
        if asset:
            operations.append(
                {
                    "op": "add_video",
                    "track": "primary",
                    "index": index,
                    "path": asset,
                    "start": offset,
                    "duration": duration,
                    "fit": "cover",
                }
            )

        voiceover = shot.get("voiceover") or shot.get("audio")
        if voiceover:
            operations.append(
                {
                    "op": "add_audio",
                    "track": "voiceover",
                    "index": index,
                    "path": str(voiceover),
                    "start": offset,
                    "duration": duration,
                    "volume": 1.0,
                }
            )

        caption = shot.get("caption") or shot.get("narration")
        if caption:
            operations.append(
                {
                    "op": "add_caption",
                    "track": "captions",
                    "index": index,
                    "text": str(caption),
                    "start": offset,
                    "duration": duration,
                    "style": _caption_style(storyboard),
                }
            )

        offset += duration

    operations.append({"op": "save"})
    return {
        "backend": backend,
        "locale": lang,
        "draft_name": title,
        "draft_root": str(Path(draft_root)),
        "canvas": canvas,
        "ratio": ratio,
        "platform": platform,
        "template": storyboard.get("template") or {},
        "duration": offset,
        "source_locales": source_locales,
        "operations": operations,
    }


def build_multilingual_draft_plans(
    storyboard: dict[str, Any],
    *,
    backend: Backend,
    draft_root: str,
    draft_name: str | None = None,
) -> list[dict[str, Any]]:
    """Expand storyboard.locales into one draft plan per language."""
    source_lang = storyboard.get("lang", "zh")
    locales = storyboard.get("locales") or {}
    order = [source_lang, *[key for key in locales.keys() if key != source_lang]]
    base_name = draft_name or _safe_name(storyboard.get("title") or "ai-video")
    plans = []
    for locale in order:
        localized = _localized_storyboard(storyboard, locale)
        plans.append(
            build_draft_plan(
                localized,
                backend=backend,
                draft_root=draft_root,
                draft_name=f"{base_name}-{locale}",
            )
        )
    return plans


def write_draft_manifest(plan: dict[str, Any], output_dir: str | Path) -> str:
    """Persist a draft plan for an executor or human operator."""
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe_name(plan['draft_name'])}.{plan['backend']}.draft-plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def write_multilingual_manifests(plans: list[dict[str, Any]], output_dir: str | Path) -> list[str]:
    return [write_draft_manifest(plan, output_dir) for plan in plans]


def render_draft_manifest(
    storyboard: dict[str, Any],
    *,
    backend: Backend,
    draft_root: str,
    output_dir: str | Path,
    draft_name: str | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    """Create a draft manifest. Real editor execution is layered behind this."""
    if storyboard.get("locales"):
        plans = build_multilingual_draft_plans(
            storyboard,
            backend=backend,
            draft_root=draft_root,
            draft_name=draft_name,
        )
    else:
        plans = [
            build_draft_plan(
                storyboard,
                backend=backend,
                draft_root=draft_root,
                draft_name=draft_name,
            )
        ]
    manifest_paths = write_multilingual_manifests(plans, output_dir)
    plan = plans[0]
    result = {
        "renderer": f"{backend}_draft",
        "draft_plan_path": manifest_paths[0],
        "draft_plan_paths": manifest_paths,
        "draft_name": plan["draft_name"],
        "locales": [item["locale"] for item in plans],
        "operations": sum(len(item["operations"]) for item in plans),
    }
    if execute:
        result["execution"] = execute_draft_manifests(manifest_paths)
    return result


def execute_draft_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Execute a draft plan through pyCapCut or pyJianYingDraft if installed."""
    backend = plan.get("backend")
    editor = _load_editor_module(backend)
    canvas = plan.get("canvas") or {}
    width = int(canvas.get("width") or 1080)
    height = int(canvas.get("height") or 1920)
    draft_root = str(plan.get("draft_root") or "")
    draft_name = str(plan.get("draft_name") or "ai-video")
    if not draft_root:
        raise ValueError("draft_root is required to execute a draft plan")

    folder = editor.DraftFolder(draft_root)
    script = folder.create_draft(draft_name, width, height, allow_replace=True)
    _ensure_tracks(editor, script)

    for op in plan.get("operations") or []:
        kind = op.get("op")
        if kind == "add_video":
            script.add_segment(
                editor.VideoSegment(
                    op["path"],
                    _timerange(editor, op.get("start", 0), op.get("duration", 5)),
                )
            )
        elif kind == "add_audio":
            script.add_segment(
                editor.AudioSegment(
                    op["path"],
                    _timerange(editor, op.get("start", 0), op.get("duration", 5)),
                    volume=float(op.get("volume", 1.0)),
                )
            )
        elif kind == "add_caption":
            script.add_segment(_caption_segment(editor, op))
        elif kind in {"create_draft", "save"}:
            continue

    script.save()
    return {
        "status": "executed",
        "backend": backend,
        "draft_name": draft_name,
        "draft_root": draft_root,
        "operations": len(plan.get("operations") or []),
    }


def execute_draft_manifests(paths: list[str]) -> list[dict[str, Any]]:
    results = []
    for path in paths:
        plan = json.loads(Path(path).read_text(encoding="utf-8"))
        results.append(execute_draft_plan(plan))
    return results


def _shot_asset(shot: dict[str, Any]) -> str:
    for key in ("asset", "video_path", "video", "clip_path", "local_path"):
        value = shot.get(key)
        if value:
            return str(value)
    return ""


def _load_editor_module(backend: str):
    if backend == "capcut":
        module_name = "pycapcut"
    elif backend == "jianying":
        module_name = "pyJianYingDraft"
    else:
        raise ValueError(f"unsupported draft backend: {backend}")
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"{module_name} is not installed. Install it before executing {backend} drafts."
        ) from exc


def _ensure_tracks(editor, script) -> None:
    for name in ("video", "audio", "text"):
        track = getattr(editor.TrackType, name)
        script.add_track(track)


def _timerange(editor, start: Any, duration: Any):
    return editor.trange(_seconds(start), _seconds(duration))


def _caption_segment(editor, op: dict[str, Any]):
    kwargs: dict[str, Any] = {}
    style = op.get("style") or {}
    if hasattr(editor, "TextStyle"):
        color = _hex_to_rgb(style.get("color"))
        if color:
            kwargs["style"] = editor.TextStyle(color=color)
    if hasattr(editor, "ClipSettings"):
        position = style.get("position", "lower-third-safe")
        transform_y = -0.72 if position == "lower-third-safe" else -0.2
        kwargs["clip_settings"] = editor.ClipSettings(transform_y=transform_y)
    return editor.TextSegment(
        op.get("text", ""),
        _timerange(editor, op.get("start", 0), op.get("duration", 5)),
        **kwargs,
    )


def _seconds(value: Any) -> str:
    if isinstance(value, str):
        return value
    return f"{float(value):g}s"


def _hex_to_rgb(value: Any):
    if not isinstance(value, str) or not value.startswith("#") or len(value) != 7:
        return None
    return tuple(int(value[index : index + 2], 16) / 255 for index in (1, 3, 5))


def _localized_storyboard(storyboard: dict[str, Any], locale: str) -> dict[str, Any]:
    if locale == storyboard.get("lang", "zh"):
        localized = dict(storyboard)
        localized["locales"] = {}
        return localized

    override = (storyboard.get("locales") or {}).get(locale) or {}
    localized = dict(storyboard)
    localized["lang"] = locale
    localized["title"] = override.get("title", storyboard.get("title"))
    localized["locales"] = {}
    shots = []
    override_shots = override.get("shots") or []
    for index, shot in enumerate(storyboard.get("shots") or []):
        merged = dict(shot)
        if index < len(override_shots) and isinstance(override_shots[index], dict):
            merged.update(override_shots[index])
        shots.append(merged)
    localized["shots"] = shots
    return localized


def _canvas_for_ratio(ratio: str) -> dict[str, int]:
    return {
        "9:16": {"width": 1080, "height": 1920},
        "16:9": {"width": 1920, "height": 1080},
        "1:1": {"width": 1080, "height": 1080},
    }.get(ratio, {"width": 1080, "height": 1920})


def _caption_style(storyboard: dict[str, Any]) -> dict[str, Any]:
    template = storyboard.get("template") or {}
    return {
        "position": template.get("caption_position", "lower-third-safe"),
        "font_size": int(template.get("caption_font_size", 48)),
        "color": template.get("caption_color", "#FFFFFF"),
        "outline": template.get("caption_outline", "#000000"),
    }


def _safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in value.strip())
    return safe.strip("-") or "ai-video"
