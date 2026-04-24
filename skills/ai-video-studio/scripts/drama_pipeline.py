#!/usr/bin/env python3
"""Drama pipeline — one-command scenario-based product/drama video generation.

Implements a four-layer pipeline inspired by huobao-drama methodology:
  1. Script / blueprint (characters + scenes + logline)
  2. Storyboard breakdown (shot-by-shot with character + scene consistency)
  3. Seedance video generation (handled by studio.pipeline)
  4. FFmpeg render (handled by studio.pipeline)

The first two layers run in a single Sonnet+Opus advisor loop; the advisor
picks the narrative template autonomously (问题-转折-解决 / 蒙太奇 / 剧情化).
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

SKILL_DIR = Path(__file__).resolve().parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import advisor as advisor_mod  # noqa: E402

Mode = Literal["product", "shortdrama"]


@dataclass(frozen=True)
class DramaRequest:
    mode: Mode
    idea: str
    shots: int = 6
    duration: int = 5
    ratio: str = "16:9"
    lang: str = "zh"
    scenario: str | None = None
    product_highlights: str | None = None
    max_advisor_calls: int = 3


ADVISOR_SYSTEM = (
    "You are a senior creative director for short-form video. "
    "You specialize in scenario-based product promotion AND short-drama storytelling. "
    "Be opinionated. Pick the narrative template that best fits the brief — "
    "from [问题-转折-解决, 场景蒙太奇, 故事剧情化, or a hybrid you justify] — "
    "and commit to it. Call out weak hooks and flat endings directly."
)

EXECUTOR_SYSTEM = (
    "You are a video-production AI. You produce strictly valid JSON storyboards "
    "ready for automated rendering. Every shot must be self-consistent with the "
    "characters and scenes you declare. Never invent characters or scenes inside "
    "`shots` that are not in the top-level `characters` / `scenes` arrays."
)


def _build_prompt(req: DramaRequest) -> str:
    mode_block = _mode_block(req)
    scenario_block = f"\n- Scenario constraint: {req.scenario}" if req.scenario else ""
    product_block = (
        f"\n- Product highlights (must be naturally woven in, not listed like ad copy): "
        f"{req.product_highlights}"
        if req.product_highlights
        else ""
    )

    return (
        f"{mode_block}\n\n"
        f"Brief:\n"
        f"- Core idea: \"{req.idea}\"\n"
        f"- Shot count: exactly {req.shots}\n"
        f"- Each shot duration: {req.duration}s\n"
        f"- Aspect ratio: {req.ratio}\n"
        f"- Language for caption / narration: {req.lang}"
        f"{scenario_block}"
        f"{product_block}\n\n"
        f"Consult the advisor at least once to pick + justify the narrative template, "
        f"and once more to pressure-test the shot list before finalizing.\n\n"
        f"Output JSON with this EXACT schema:\n"
        f"{_schema_hint(req)}\n\n"
        f"Rules:\n"
        f"1. The `prompt` field of each shot must be a DETAILED English text-to-video "
        f"   prompt for Seedance 2.0. Include: subject, action, camera movement, "
        f"   lighting, mood. 40-80 words. No commas-only lists.\n"
        f"2. When the shot involves a character from the top-level `characters` array, "
        f"   embed the character's appearance description INLINE in the prompt so "
        f"   Seedance renders them consistently across shots.\n"
        f"3. When the shot uses a scene from `scenes`, embed its location + time + "
        f"   atmosphere description INLINE.\n"
        f"4. `caption` and `narration` stay in {req.lang}. `caption` is on-screen "
        f"   text (punchy, ≤15 chars for {req.lang}='zh'). `narration` is voice-over "
        f"   (one sentence).\n"
        f"5. Total runtime must equal {req.shots * req.duration}s.\n"
        f"6. Output ONLY the JSON object. No markdown fences, no commentary."
    )


def _mode_block(req: DramaRequest) -> str:
    if req.mode == "product":
        return (
            "Mission: scenario-based PRODUCT PROMOTION short video. Pick the best "
            "narrative template based on the product type — don't default. "
            "The product must earn its screen time; avoid obvious ad-speak."
        )
    return (
        "Mission: SHORT DRAMA. Two to three characters max. One clear emotional "
        "turn. The payoff has to land in the final 1-2 shots. No narrator "
        "exposition — show, don't tell."
    )


def _schema_hint(req: DramaRequest) -> str:
    return json.dumps(
        {
            "title": "string",
            "mode": req.mode,
            "logline": "one-sentence summary",
            "narrative_template": "问题-转折-解决 | 场景蒙太奇 | 故事剧情化 | hybrid:<justify>",
            "ratio": req.ratio,
            "lang": req.lang,
            "tts": True,
            "characters": [
                {
                    "id": 1,
                    "name": "string",
                    "appearance": "200-400 chars, specific: gender/age/build/hair/outfit",
                    "role": "主角|配角|龙套",
                }
            ],
            "scenes": [
                {
                    "id": 1,
                    "location": "string",
                    "time": "string e.g. 黄昏/清晨/深夜",
                    "atmosphere": "lighting + color tone + mood",
                }
            ],
            "shots": [
                {
                    "prompt": "detailed EN Seedance prompt with inline character+scene descriptors",
                    "duration": req.duration,
                    "caption": f"short {req.lang} on-screen text",
                    "narration": f"one {req.lang} sentence voice-over",
                    "character_ids": [1],
                    "scene_id": 1,
                }
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    # Prefer fenced block, then greedy braces.
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    candidates = [fenced.group(1)] if fenced else []
    # Greedy outermost braces.
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(text[first : last + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    return None


def _validate(blueprint: dict[str, Any], req: DramaRequest) -> list[str]:
    errors: list[str] = []
    shots = blueprint.get("shots")
    if not isinstance(shots, list) or len(shots) != req.shots:
        errors.append(f"shots length must be {req.shots}, got {len(shots) if isinstance(shots, list) else 'n/a'}")
    if isinstance(shots, list):
        char_ids = {c.get("id") for c in blueprint.get("characters") or [] if isinstance(c, dict)}
        scene_ids = {s.get("id") for s in blueprint.get("scenes") or [] if isinstance(s, dict)}
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict):
                errors.append(f"shot[{i}] is not an object")
                continue
            if not shot.get("prompt"):
                errors.append(f"shot[{i}].prompt missing")
            for cid in shot.get("character_ids") or []:
                if cid not in char_ids:
                    errors.append(f"shot[{i}] references unknown character_id={cid}")
            sid = shot.get("scene_id")
            if sid is not None and sid not in scene_ids:
                errors.append(f"shot[{i}] references unknown scene_id={sid}")
    return errors


def generate_drama(req: DramaRequest) -> dict[str, Any]:
    """Run the advisor-driven blueprint+storyboard generation.

    Returns a storyboard dict compatible with `studio.run_pipeline`. Extra
    fields (`characters`, `scenes`, `narrative_template`, `logline`) are kept
    for traceability but ignored by the renderer.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var required for drama generation")

    client = advisor_mod.AdvisorClient(api_key=api_key, advisor_system=ADVISOR_SYSTEM)
    prompt = _build_prompt(req)

    result = client.run(
        prompt,
        executor="claude-sonnet-4-6",
        advisor="claude-opus-4-6",
        max_advisor_calls=req.max_advisor_calls,
        system=EXECUTOR_SYSTEM,
    )

    blueprint = _extract_json(result.text)
    if blueprint is None:
        return {
            "raw_response": result.text,
            "advisor_log": result.advisor_log,
            "error": "could not extract JSON",
        }

    errors = _validate(blueprint, req)
    if errors:
        blueprint.setdefault("_warnings", []).extend(errors)

    # Ensure fields the downstream pipeline expects.
    blueprint.setdefault("ratio", req.ratio)
    blueprint.setdefault("lang", req.lang)
    blueprint.setdefault("tts", True)
    blueprint["_advisor_meta"] = {
        "calls": result.advisor_calls,
        "turns": result.turns,
        "input_tokens": result.total_input_tokens,
        "output_tokens": result.total_output_tokens,
    }
    return blueprint
