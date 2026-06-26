"""Local creative-copy adapter for multilingual social video drafts.

The default adapter is rule-based and works without API keys. Future local LLM
or commercial model adapters can return the same copy matrix shape.
"""
from __future__ import annotations

from typing import Any


SLOT_IDS = ("hook", "benefit", "cta")


def build_copy_matrix(
    brief: dict[str, Any],
    *,
    platforms: list[str] | None = None,
    locales: list[str] | None = None,
    variants: int = 3,
) -> list[dict[str, Any]]:
    platform_order = platforms or [""]
    locale_order = locales or ["zh", "en"]
    count = max(1, int(variants))
    matrix = []
    for platform in platform_order:
        for variant in range(1, count + 1):
            for locale in locale_order:
                matrix.append(
                    {
                        "platform": platform,
                        "locale": locale,
                        "variant": variant,
                        "slots": _slots(brief, platform, locale, variant),
                    }
                )
    return matrix


def find_copy(
    matrix: list[dict[str, Any]],
    *,
    platform: str,
    locale: str,
    variant: int,
) -> dict[str, Any]:
    for item in matrix:
        if item["platform"] == platform and item["locale"] == locale and item["variant"] == variant:
            return item
    raise KeyError(f"copy not found: platform={platform} locale={locale} variant={variant}")


def _slots(
    brief: dict[str, Any],
    platform: str,
    locale: str,
    variant: int,
) -> list[dict[str, str]]:
    context = _context(brief, variant)
    if locale == "en":
        texts = [
            _en_hook(platform, context),
            f"{context['benefit_en']}, {context['second_benefit_en']}",
            context["cta_en"],
        ]
    else:
        texts = [
            _zh_hook(platform, context),
            f"{context['benefit']}，{context['second_benefit']}",
            context["cta"],
        ]
    forbidden = [str(item) for item in brief.get("forbidden_words") or []]
    return [{"id": slot_id, "text": _sanitize(text, forbidden)} for slot_id, text in zip(SLOT_IDS, texts)]


def _context(brief: dict[str, Any], variant: int) -> dict[str, str]:
    points = [str(item) for item in brief.get("selling_points") or []] or ["核心卖点"]
    offset = (variant - 1) % len(points)
    rotated = points[offset:] + points[:offset]
    product = str(brief.get("product_name") or "产品")
    audience = str(brief.get("audience") or "目标用户")
    cta = str(brief.get("cta") or "了解更多")
    first = rotated[0]
    second = rotated[1] if len(rotated) > 1 else rotated[0]
    return {
        "product": product,
        "product_en": _english_product(product),
        "audience": audience,
        "benefit": first,
        "second_benefit": second,
        "benefit_en": _english_benefit(first),
        "second_benefit_en": _english_benefit(second),
        "cta": cta,
        "cta_en": _english_cta(cta),
    }


def _zh_hook(platform: str, context: dict[str, str]) -> str:
    if platform == "tiktok":
        return f"{context['audience']}，3秒看懂{context['product']}值不值"
    if platform == "shorts":
        return f"15秒看{context['product']}解决什么问题"
    if platform == "reels":
        return f"今天的通勤装备：{context['product']}"
    return f"{context['audience']}刷到这个{context['product']}先别划走"


def _en_hook(platform: str, context: dict[str, str]) -> str:
    if platform == "tiktok":
        return f"3-second test: {context['product_en']} for commuters"
    if platform == "shorts":
        return f"{context['product_en']} in 15 seconds"
    if platform == "reels":
        return f"POV: your commute gets a {context['product_en']}"
    return f"Stop scrolling: {context['product_en']} for commuters"


def _sanitize(text: str, forbidden_words: list[str]) -> str:
    cleaned = text
    for word in forbidden_words:
        cleaned = cleaned.replace(word, "")
    return " ".join(cleaned.split())


def _english_product(product: str) -> str:
    return {"智能保温杯": "Smart Mug"}.get(product, product)


def _english_benefit(text: str) -> str:
    return {
        "12小时保温": "12-hour heat retention",
        "一键开盖": "one-tap lid",
    }.get(text, text)


def _english_cta(text: str) -> str:
    return {"现在领取试用": "Claim your trial now"}.get(text, text)
