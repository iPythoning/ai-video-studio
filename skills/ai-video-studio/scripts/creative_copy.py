"""Local creative-copy adapter for multilingual social video drafts.

The default adapter is rule-based and works without API keys. Future local LLM
or commercial model adapters can return the same copy matrix shape.
"""
from __future__ import annotations

import os
import subprocess
import json
import shlex
from typing import Any, Callable


SLOT_IDS = ("hook", "benefit", "cta")
CopyAdapter = Callable[[dict[str, Any], list[str], list[str], int], list[dict[str, Any]]]
_ADAPTERS: dict[str, CopyAdapter] = {}


def build_copy_matrix(
    brief: dict[str, Any],
    *,
    platforms: list[str] | None = None,
    locales: list[str] | None = None,
    variants: int = 3,
    adapter: str = "local",
) -> list[dict[str, Any]]:
    platform_order = platforms or [""]
    locale_order = locales or ["zh", "en"]
    count = max(1, int(variants))
    selected = _adapter(adapter)
    if selected is not _local_rules_adapter:
        return _tag_adapter(selected(brief, platform_order, locale_order, count), adapter)
    return _tag_adapter(_local_rules_adapter(brief, platform_order, locale_order, count), adapter)


def register_copy_adapter(name: str, adapter: CopyAdapter) -> None:
    if not name:
        raise ValueError("adapter name is required")
    _ADAPTERS[name] = adapter


def unregister_copy_adapter(name: str) -> None:
    _ADAPTERS.pop(name, None)


def available_adapters() -> list[str]:
    return sorted(["local", "local_rules", "local_llm", "anthropic", "doubao", *_ADAPTERS.keys()])


def _adapter(name: str) -> CopyAdapter:
    if name in ("", "local", "local_rules"):
        return _local_rules_adapter
    if name in _ADAPTERS:
        return _ADAPTERS[name]
    if name in {"local_llm", "anthropic", "doubao"}:
        return _command_adapter(name)
    raise ValueError(f"unknown creative copy adapter: {name}. Available: {', '.join(available_adapters())}")


def _local_rules_adapter(
    brief: dict[str, Any],
    platform_order: list[str],
    locale_order: list[str],
    count: int,
) -> list[dict[str, Any]]:
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


def _command_adapter(name: str) -> CopyAdapter:
    env_name = f"CREATIVE_COPY_{name.upper()}_COMMAND"
    command = os.environ.get(env_name, "")
    if not command:
        raise RuntimeError(f"{env_name} is required to use creative copy adapter '{name}'")

    def run_command(
        brief: dict[str, Any],
        platforms: list[str],
        locales: list[str],
        variants: int,
    ) -> list[dict[str, Any]]:
        payload = {
            "brief": brief,
            "platforms": platforms,
            "locales": locales,
            "variants": variants,
        }
        result = subprocess.run(
            shlex.split(command),
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise ValueError(f"{env_name} must output a JSON list")
        return data

    return run_command


def _tag_adapter(matrix: list[dict[str, Any]], adapter: str) -> list[dict[str, Any]]:
    source = adapter or "local"
    for item in matrix:
        item.setdefault("source_adapter", source)
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
