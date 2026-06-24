"""AI Video Studio — HTTP service.

Thin FastAPI shell over the `drama` pipeline so an agent (content-factory's
AI COO) can request a finished video via one POST instead of the CLI.

Flow mirrors `studio.py drama --run`:
    generate_drama(req) -> blueprint(shots) -> run_pipeline -> mp4 on disk
The rendered file is served from MEDIA_DIR at /media, so the response carries
a fetchable mp4_url (what content-factory's VideoGenerator expects).

Run:  uvicorn server:app --host 0.0.0.0 --port 8001
Env:  PUBLIC_BASE_URL (how callers reach this service, for building mp4_url),
      plus studio.py's keys (SEEDANCE_API_KEY, ANTHROPIC_API_KEY, MEDIA_DIR).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import studio
import drama_pipeline as dp
import draft_backend
import draft_templates
import social_replies

_log = logging.getLogger("video_studio")
MEDIA_DIR: Path = studio.MEDIA_DIR
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8001")

app = FastAPI(title="AI Video Studio", version="0.1.0")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


class GenerateRequest(BaseModel):
    idea: str
    # Literal — validated at the API boundary; also keeps `mode` safe to put in a
    # filename (no path traversal: anything off-list is rejected with 422).
    mode: Literal["product", "shortdrama"] = "product"
    highlights: str | None = None
    scenario: str | None = None
    ratio: str = "9:16"
    lang: str = "zh"
    shots: int = 6
    duration: int = 5              # 5 | 8 | 11
    max_advisor_calls: int = 3


class GenerateResponse(BaseModel):
    mp4_url: str
    renderer: str
    shots: int
    blueprint_path: str


class BlueprintResponse(BaseModel):
    shots: int
    blueprint_path: str
    blueprint: dict


class DraftRequest(GenerateRequest):
    backend: Literal["capcut", "jianying"] = "capcut"
    draft_root: str | None = None
    draft_name: str | None = None
    execute: bool = False


class DraftResponse(BaseModel):
    renderer: str
    draft_plan_path: str
    draft_plan_paths: list[str]
    locales: list[str]
    operations: int
    execution: list[dict] | None = None


class TemplateDraftRequest(BaseModel):
    brief: dict
    assets: list[str]
    backend: Literal["capcut", "jianying"] = "capcut"
    draft_root: str | None = None
    template_id: str = "ugc_hook_cta"
    locales: list[str] = Field(default_factory=lambda: ["zh", "en"])
    variants: int = 3
    execute: bool = False


class TemplateDraftResponse(BaseModel):
    renderer: str
    template_id: str
    variants: int
    locales: list[str]
    draft_plan_paths: list[str]
    outputs: list[dict]


class SocialReplyRequest(BaseModel):
    comments: list[dict]
    db_path: str | None = None
    brand_name: str = ""
    product_url: str = ""
    human_review_terms: list[str] | None = None


class SocialReplyResponse(BaseModel):
    db_path: str
    ingest: dict[str, int]
    planned: int
    jobs: list[dict]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "media_dir": str(MEDIA_DIR)}


def _build_blueprint(req: GenerateRequest) -> tuple[dict, Path]:
    """Layers 1-2 only (Sonnet+Opus advisor). No Seedance, no render — cheap."""
    dr = dp.DramaRequest(
        mode=req.mode, idea=req.idea, shots=req.shots, duration=req.duration,
        ratio=req.ratio, lang=req.lang, scenario=req.scenario,
        product_highlights=req.highlights, max_advisor_calls=req.max_advisor_calls,
    )
    blueprint = dp.generate_drama(dr)
    if blueprint.get("error") or "shots" not in blueprint:
        raise RuntimeError(f"blueprint failed: {blueprint.get('error', 'no shots')}")
    bp_path = MEDIA_DIR / f"drama-{req.mode}-{int(time.time())}.json"
    bp_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
    return blueprint, bp_path


def _run_drama(req: GenerateRequest) -> dict:
    """Blocking: blueprint -> Seedance generation -> render. Run off the loop."""
    blueprint, bp_path = _build_blueprint(req)
    result = studio.run_pipeline(str(bp_path))
    if not result or not result.get("video_path"):
        raise RuntimeError(f"render produced no mp4: {result}")
    return {"result": result, "blueprint_path": str(bp_path), "shots": len(blueprint["shots"])}


def _plan_social_replies(req: SocialReplyRequest) -> dict:
    db_path = req.db_path or str(MEDIA_DIR / "social-replies.sqlite")
    policy = social_replies.ReplyPolicy(
        brand_name=req.brand_name,
        product_url=req.product_url,
        human_review_terms=tuple(req.human_review_terms)
        if req.human_review_terms
        else social_replies.ReplyPolicy().human_review_terms,
    )
    with social_replies.CommentStore(db_path) as store:
        ingest = store.ingest(req.comments)
        jobs = store.plan_reply_jobs(policy)
    return {"db_path": db_path, "ingest": ingest, "planned": len(jobs), "jobs": jobs}


def _render_template_draft(req: TemplateDraftRequest) -> dict:
    draft_root = req.draft_root or os.environ.get(
        "CAPCUT_DRAFT_ROOT" if req.backend == "capcut" else "JIANYING_DRAFT_ROOT",
        str(MEDIA_DIR / f"{req.backend}-drafts"),
    )
    result = draft_templates.render_template_draft_package(
        req.brief,
        req.assets,
        backend=req.backend,
        draft_root=draft_root,
        output_dir=MEDIA_DIR,
        template_id=req.template_id,
        locales=req.locales,
        variants=req.variants,
        execute=req.execute,
    )
    return {"renderer": f"{req.backend}_draft", **result}


@app.post("/blueprint", response_model=BlueprintResponse)
async def blueprint(req: GenerateRequest) -> BlueprintResponse:
    """Dry-run: storyboard only (ANTHROPIC_API_KEY), zero Seedance spend."""
    try:
        bp, bp_path = await asyncio.to_thread(_build_blueprint, req)
    except Exception as e:
        _log.exception("blueprint_failed")
        raise HTTPException(status_code=500, detail=type(e).__name__) from e
    return BlueprintResponse(shots=len(bp["shots"]), blueprint_path=str(bp_path), blueprint=bp)


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    try:
        out = await asyncio.to_thread(_run_drama, req)
    except Exception as e:
        # Don't leak str(e) to the caller — it can embed Seedance/Anthropic keys.
        _log.exception("generate_failed")
        raise HTTPException(status_code=500, detail=type(e).__name__) from e

    filename = Path(out["result"]["video_path"]).name
    return GenerateResponse(
        mp4_url=f"{PUBLIC_BASE_URL.rstrip('/')}/media/{filename}",
        renderer=out["result"].get("renderer", "ffmpeg"),
        shots=out["shots"],
        blueprint_path=out["blueprint_path"],
    )


@app.post("/draft", response_model=DraftResponse)
async def draft(req: DraftRequest) -> DraftResponse:
    """Create Jianying/CapCut draft manifests. No Seedance render required."""
    try:
        bp, _ = await asyncio.to_thread(_build_blueprint, req)
        draft_root = req.draft_root or os.environ.get(
            "CAPCUT_DRAFT_ROOT" if req.backend == "capcut" else "JIANYING_DRAFT_ROOT",
            str(MEDIA_DIR / f"{req.backend}-drafts"),
        )
        result = draft_backend.render_draft_manifest(
            bp,
            backend=req.backend,
            draft_root=draft_root,
            output_dir=MEDIA_DIR,
            draft_name=req.draft_name or bp.get("title", "ai-video"),
            execute=req.execute,
        )
    except Exception as e:
        _log.exception("draft_failed")
        raise HTTPException(status_code=500, detail=type(e).__name__) from e
    return DraftResponse(**result)


@app.post("/draft/template", response_model=TemplateDraftResponse)
async def template_draft(req: TemplateDraftRequest) -> TemplateDraftResponse:
    """Create multilingual template draft manifests from real-shot assets."""
    try:
        result = await asyncio.to_thread(_render_template_draft, req)
    except Exception as e:
        _log.exception("template_draft_failed")
        raise HTTPException(status_code=500, detail=type(e).__name__) from e
    return TemplateDraftResponse(**result)


@app.post("/social/replies/plan", response_model=SocialReplyResponse)
async def social_replies_plan(req: SocialReplyRequest) -> SocialReplyResponse:
    """Normalize comment exports and create reviewable reply jobs. No sender."""
    try:
        result = await asyncio.to_thread(_plan_social_replies, req)
    except Exception as e:
        _log.exception("social_replies_plan_failed")
        raise HTTPException(status_code=500, detail=type(e).__name__) from e
    return SocialReplyResponse(**result)
