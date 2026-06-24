"""Local multilingual draft templates for CapCut/Jianying backends."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import draft_backend


BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "ugc_hook_cta": {
        "ratio": "9:16",
        "renderer": "capcut_draft",
        "template": {
            "id": "ugc_hook_cta",
            "caption_position": "lower-third-safe",
            "caption_font_size": 52,
            "caption_color": "#FFFFFF",
            "caption_outline": "#000000",
        },
        "slots": [
            {
                "id": "hook",
                "duration": 3,
                "zh": "{audience}刷到这个{product}先别划走",
                "en": "Stop scrolling: {product_en} for commuters",
            },
            {
                "id": "benefit",
                "duration": 7,
                "zh": "{benefit}，{second_benefit}",
                "en": "{benefit_en}, {second_benefit_en}",
            },
            {
                "id": "cta",
                "duration": 5,
                "zh": "{cta}",
                "en": "{cta_en}",
            },
        ],
    }
}


def build_template_storyboards(
    brief: dict[str, Any],
    assets: list[str],
    *,
    template_id: str = "ugc_hook_cta",
    locales: list[str] | None = None,
    variants: int = 3,
) -> list[dict[str, Any]]:
    if not assets:
        raise ValueError("at least one asset is required")
    template = _template(template_id)
    locales = locales or ["zh", "en"]
    base_lang = locales[0]
    count = max(1, int(variants))
    storyboards = []
    for variant_index in range(count):
        context = _context(brief, variant_index)
        shots = _shots_for_locale(template, assets, base_lang, context)
        storyboard = {
            "title": brief.get("title") or brief.get("product_name") or "Template Draft",
            "draft_name": f"{_slug(brief, variant_index)}-v{variant_index + 1}",
            "ratio": template.get("ratio", "9:16"),
            "renderer": template.get("renderer", "capcut_draft"),
            "lang": base_lang,
            "template": dict(template["template"]),
            "shots": shots,
            "locales": {},
        }
        for locale in locales[1:]:
            storyboard["locales"][locale] = {
                "title": _localized_title(brief, locale),
                "shots": _shots_for_locale(template, assets, locale, context, include_assets=False),
            }
        storyboards.append(_sanitize_storyboard(storyboard, brief.get("forbidden_words") or []))
    return storyboards


def render_template_draft_package(
    brief: dict[str, Any],
    assets: list[str],
    *,
    backend: draft_backend.Backend,
    draft_root: str,
    output_dir: str | Path,
    template_id: str = "ugc_hook_cta",
    locales: list[str] | None = None,
    variants: int = 3,
    execute: bool = False,
) -> dict[str, Any]:
    storyboards = build_template_storyboards(
        brief,
        assets,
        template_id=template_id,
        locales=locales,
        variants=variants,
    )
    outputs = []
    paths: list[str] = []
    for index, storyboard in enumerate(storyboards, start=1):
        rendered = draft_backend.render_draft_manifest(
            storyboard,
            backend=backend,
            draft_root=draft_root,
            output_dir=output_dir,
            draft_name=storyboard["draft_name"],
            execute=execute,
        )
        outputs.append({"variant": index, **rendered})
        paths.extend(rendered["draft_plan_paths"])
    return {
        "template_id": template_id,
        "variants": len(storyboards),
        "locales": locales or ["zh", "en"],
        "draft_plan_paths": paths,
        "outputs": outputs,
    }


def _template(template_id: str) -> dict[str, Any]:
    if template_id not in BUILTIN_TEMPLATES:
        raise ValueError(f"unknown template: {template_id}")
    return BUILTIN_TEMPLATES[template_id]


def _shots_for_locale(
    template: dict[str, Any],
    assets: list[str],
    locale: str,
    context: dict[str, str],
    *,
    include_assets: bool = True,
) -> list[dict[str, Any]]:
    shots = []
    for index, slot in enumerate(template["slots"]):
        caption = _render(slot.get(locale) or slot.get("en") or slot.get("zh") or "", context)
        shot = {
            "duration": slot.get("duration", 5),
            "caption": caption,
            "narration": caption,
        }
        if include_assets:
            shot["asset"] = assets[index % len(assets)]
        shots.append(shot)
    return shots


def _context(brief: dict[str, Any], variant_index: int) -> dict[str, str]:
    points = [str(item) for item in brief.get("selling_points") or []] or ["核心卖点"]
    rotated = points[variant_index % len(points) :] + points[: variant_index % len(points)]
    product = str(brief.get("product_name") or "产品")
    brand = str(brief.get("brand_name") or "")
    audience = str(brief.get("audience") or "目标用户")
    cta = str(brief.get("cta") or "了解更多")
    return {
        "product": product,
        "product_en": _english_product(product),
        "brand": brand,
        "audience": audience,
        "benefit": rotated[0],
        "second_benefit": rotated[1] if len(rotated) > 1 else rotated[0],
        "benefit_en": _english_benefit(rotated[0]),
        "second_benefit_en": _english_benefit(rotated[1] if len(rotated) > 1 else rotated[0]),
        "cta": cta,
        "cta_en": _english_cta(cta),
    }


def _render(template: str, context: dict[str, str]) -> str:
    return template.format(**context)


def _localized_title(brief: dict[str, Any], locale: str) -> str:
    if locale == "en":
        return str(brief.get("title_en") or brief.get("product_name_en") or _english_product(str(brief.get("product_name") or "Product")))
    return str(brief.get("title") or brief.get("product_name") or "Template Draft")


def _sanitize_storyboard(storyboard: dict[str, Any], forbidden_words: list[Any]) -> dict[str, Any]:
    words = [str(item) for item in forbidden_words if str(item)]
    if not words:
        return storyboard
    for shot in storyboard.get("shots", []):
        _sanitize_shot(shot, words)
    for locale in (storyboard.get("locales") or {}).values():
        for shot in locale.get("shots", []):
            _sanitize_shot(shot, words)
    return storyboard


def _sanitize_shot(shot: dict[str, Any], words: list[str]) -> None:
    for key in ("caption", "narration"):
        value = str(shot.get(key) or "")
        for word in words:
            value = value.replace(word, "")
        shot[key] = " ".join(value.split())


def _slug(brief: dict[str, Any], variant_index: int) -> str:
    base = str(brief.get("slug") or brief.get("product_name_en") or brief.get("product_name") or "campaign")
    aliases = {"智能保温杯": "smart-mug"}
    base = aliases.get(base, base)
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in base)
    return safe.strip("-") or f"campaign-{variant_index + 1}"


def _english_product(product: str) -> str:
    return {"智能保温杯": "Smart Mug"}.get(product, product)


def _english_benefit(text: str) -> str:
    return {
        "12小时保温": "12-hour heat retention",
        "一键开盖": "one-tap lid",
    }.get(text, text)


def _english_cta(text: str) -> str:
    return {"现在领取试用": "Claim your trial now"}.get(text, text)
