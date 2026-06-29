"""Local multilingual draft templates for CapCut/Jianying backends."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import creative_copy
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


PLATFORM_PROFILES: dict[str, dict[str, Any]] = {
    "tiktok": {
        "caption_position": "lower-third-safe",
        "safe_zones": {"top": 160, "bottom": 340, "left": 48, "right": 180},
        "max_duration": 45,
    },
    "reels": {
        "caption_position": "lower-third-safe",
        "safe_zones": {"top": 180, "bottom": 320, "left": 48, "right": 120},
        "max_duration": 45,
    },
    "shorts": {
        "caption_position": "lower-third-safe",
        "safe_zones": {"top": 160, "bottom": 300, "left": 48, "right": 120},
        "max_duration": 45,
    },
}


def build_template_storyboards(
    brief: dict[str, Any],
    assets: list[str],
    *,
    template_id: str = "ugc_hook_cta",
    locales: list[str] | None = None,
    platforms: list[str] | None = None,
    variants: int = 3,
    creative_copy_mode: str = "",
) -> list[dict[str, Any]]:
    if not assets:
        raise ValueError("at least one asset is required")
    template = _template(template_id)
    locales = locales or ["zh", "en"]
    base_lang = locales[0]
    count = max(1, int(variants))
    storyboards = []
    platform_order = platforms or [""]
    copy_matrix = (
        creative_copy.build_copy_matrix(
            brief,
            platforms=platform_order,
            locales=locales,
            variants=count,
            adapter=creative_copy_mode,
        )
        if creative_copy_mode
        else []
    )
    for platform in platform_order:
        for variant_index in range(count):
            context = _context(brief, variant_index)
            profile = _platform_profile(platform)
            variant = variant_index + 1
            shots = _shots_for_locale(
                template,
                assets,
                base_lang,
                context,
                copy_entry=_copy_entry(copy_matrix, platform, base_lang, variant),
            )
            storyboard = {
                "title": brief.get("title") or brief.get("product_name") or "Template Draft",
                "draft_name": _draft_name(brief, variant_index, platform),
                "ratio": template.get("ratio", "9:16"),
                "renderer": template.get("renderer", "capcut_draft"),
                "lang": base_lang,
                "variant": variant,
                "copy_source": creative_copy_mode,
                "template": _template_with_profile(template, platform, profile),
                "shots": shots,
                "locales": {},
            }
            if platform:
                storyboard["platform"] = platform
            for locale in locales[1:]:
                storyboard["locales"][locale] = {
                    "title": _localized_title(brief, locale),
                    "shots": _shots_for_locale(
                        template,
                        assets,
                        locale,
                        context,
                        include_assets=False,
                        copy_entry=_copy_entry(copy_matrix, platform, locale, variant),
                    ),
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
    platforms: list[str] | None = None,
    variants: int = 3,
    execute: bool = False,
    creative_copy_mode: str = "",
) -> dict[str, Any]:
    storyboards = build_template_storyboards(
        brief,
        assets,
        template_id=template_id,
        locales=locales,
        platforms=platforms,
        variants=variants,
        creative_copy_mode=creative_copy_mode,
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
        outputs.append(
            {
                "variant": storyboard.get("variant", index),
                "platform": storyboard.get("platform", ""),
                **rendered,
            }
        )
        paths.extend(rendered["draft_plan_paths"])
    return {
        "template_id": template_id,
        "variants": variants,
        "locales": locales or ["zh", "en"],
        "platforms": platforms or [],
        "copy_source": creative_copy_mode,
        "draft_plan_paths": paths,
        "outputs": outputs,
    }


def _template(template_id: str) -> dict[str, Any]:
    if template_id not in BUILTIN_TEMPLATES:
        raise ValueError(f"unknown template: {template_id}")
    return BUILTIN_TEMPLATES[template_id]


def _platform_profile(platform: str) -> dict[str, Any]:
    if not platform:
        return {}
    if platform not in PLATFORM_PROFILES:
        raise ValueError(f"unknown platform: {platform}")
    return PLATFORM_PROFILES[platform]


def _template_with_profile(
    template: dict[str, Any],
    platform: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(template["template"])
    if profile:
        merged["platform"] = platform
        merged["caption_position"] = profile["caption_position"]
        merged["safe_zones"] = dict(profile["safe_zones"])
        merged["max_duration"] = profile["max_duration"]
    return merged


def _shots_for_locale(
    template: dict[str, Any],
    assets: list[str],
    locale: str,
    context: dict[str, str],
    *,
    include_assets: bool = True,
    copy_entry: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    shots = []
    slot_texts = _slot_texts(copy_entry)
    for index, slot in enumerate(template["slots"]):
        caption = slot_texts.get(slot["id"]) or _render(
            slot.get(locale) or slot.get("en") or slot.get("zh") or "",
            context,
        )
        shot = {
            "duration": slot.get("duration", 5),
            "caption": caption,
            "narration": caption,
        }
        if include_assets:
            shot["asset"] = assets[index % len(assets)]
        shots.append(shot)
    return shots


def _copy_entry(
    matrix: list[dict[str, Any]],
    platform: str,
    locale: str,
    variant: int,
) -> dict[str, Any] | None:
    if not matrix:
        return None
    return creative_copy.find_copy(matrix, platform=platform, locale=locale, variant=variant)


def _slot_texts(copy_entry: dict[str, Any] | None) -> dict[str, str]:
    if not copy_entry:
        return {}
    return {str(slot["id"]): str(slot["text"]) for slot in copy_entry.get("slots", [])}


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


def _draft_name(brief: dict[str, Any], variant_index: int, platform: str) -> str:
    parts = [_slug(brief, variant_index)]
    if platform:
        parts.append(platform)
    parts.append(f"v{variant_index + 1}")
    return "-".join(parts)


def _english_product(product: str) -> str:
    return {"智能保温杯": "Smart Mug"}.get(product, product)


def _english_benefit(text: str) -> str:
    return {
        "12小时保温": "12-hour heat retention",
        "一键开盖": "one-tap lid",
    }.get(text, text)


def _english_cta(text: str) -> str:
    return {"现在领取试用": "Claim your trial now"}.get(text, text)
