"""Cross-platform social comment reply planning.

The sender layer stays outside this module. Here we only normalize comments,
dedupe them, and create reviewable reply jobs.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence, cast


RawComment = Mapping[str, object]
ReplyPlanner = Callable[[dict[str, object], "ReplyPolicy"], str]


@dataclass(frozen=True)
class ReplyPolicy:
    brand_name: str = ""
    product_url: str = ""
    human_review_terms: tuple[str, ...] = (
        "退款",
        "投诉",
        "维权",
        "假货",
        "scam",
        "refund",
        "chargeback",
        "lawsuit",
    )


class CommentStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def ingest(self, raw_comments: list[RawComment]) -> dict[str, int]:
        inserted = 0
        duplicates = 0
        skipped = 0
        for raw in raw_comments:
            comment = normalize_comment(raw)
            if not comment:
                skipped += 1
                continue
            try:
                self.conn.execute(
                    """
                    INSERT INTO comments (
                        platform, comment_id, post_id, author, text, created_at, source_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        comment["platform"],
                        comment["comment_id"],
                        comment["post_id"],
                        comment["author"],
                        comment["text"],
                        comment["created_at"],
                        json.dumps(dict(raw), ensure_ascii=False, default=str),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        self.conn.commit()
        return {"inserted": inserted, "duplicates": duplicates, "skipped": skipped}

    def plan_reply_jobs(
        self,
        policy: ReplyPolicy,
        planner: ReplyPlanner | None = None,
    ) -> list[dict[str, object]]:
        planner = planner or default_reply_planner
        jobs: list[dict[str, object]] = []
        rows = self.conn.execute(
            """
            SELECT c.*
            FROM comments c
            LEFT JOIN reply_jobs j ON j.comment_row_id = c.id
            WHERE j.id IS NULL
            ORDER BY c.id
            """
        ).fetchall()
        for row in rows:
            comment = dict(row)
            status, reason = _policy_status(str(comment["text"]), policy)
            draft = "" if status == "needs_human" else planner(comment, policy)
            self.conn.execute(
                """
                INSERT INTO reply_jobs (
                    comment_row_id, platform, comment_id, status, draft_reply, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comment["id"],
                    comment["platform"],
                    comment["comment_id"],
                    status,
                    draft,
                    reason,
                    _now_iso(),
                ),
            )
            jobs.append(
                {
                    "platform": comment["platform"],
                    "comment_id": comment["comment_id"],
                    "post_id": comment["post_id"],
                    "author": comment["author"],
                    "text": comment["text"],
                    "status": status,
                    "draft_reply": draft,
                    "reason": reason,
                }
            )
        self.conn.commit()
        return jobs

    def list_reply_jobs(self, status: str | None = None) -> list[dict[str, object]]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM reply_jobs WHERE status = ? ORDER BY id",
                (status,),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM reply_jobs ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                comment_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source_json TEXT NOT NULL,
                UNIQUE(platform, comment_id)
            );

            CREATE TABLE IF NOT EXISTS reply_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_row_id INTEGER NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                comment_id TEXT NOT NULL,
                status TEXT NOT NULL,
                draft_reply TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(comment_row_id) REFERENCES comments(id)
            );
            """
        )
        self.conn.commit()


def normalize_comment(raw: RawComment) -> dict[str, str] | None:
    platform = _first_text(raw, "platform", "source", "channel").lower()
    text = _first_text(raw, "text", "content", "comment", "message")
    if not platform or not text:
        return None
    comment_id = _first_text(raw, "comment_id", "id", "cid")
    post_id = _first_text(raw, "post_id", "video_id", "media_id", "aweme_id", "shortcode")
    author = _author(raw)
    if not comment_id:
        comment_id = _stable_id(platform, post_id, author, text)
    return {
        "platform": platform,
        "comment_id": comment_id,
        "post_id": post_id or "unknown",
        "author": author or "unknown",
        "text": text.strip(),
        "created_at": _first_text(raw, "created_at", "create_time", "timestamp") or _now_iso(),
    }


def plan_reply_workflow(
    comments_path: str | Path,
    db_path: str | Path,
    policy: ReplyPolicy | None = None,
) -> dict[str, object]:
    store = CommentStore(db_path)
    raw_comments = load_comments(comments_path)
    ingest = store.ingest(raw_comments)
    jobs = store.plan_reply_jobs(policy or ReplyPolicy())
    return {"ingest": ingest, "planned": len(jobs), "jobs": jobs}


def load_comments(path: str | Path) -> list[RawComment]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [cast(RawComment, item) for item in data if isinstance(item, Mapping)]
    if isinstance(data, Mapping):
        for key in ("comments", "items", "data"):
            items = data.get(key)
            if isinstance(items, list):
                return [cast(RawComment, item) for item in items if isinstance(item, Mapping)]
    raise ValueError("comments JSON must be a list or contain comments/items/data")


def default_reply_planner(comment: dict[str, object], policy: ReplyPolicy) -> str:
    text = str(comment.get("text", "")).lower()
    brand = policy.brand_name or "我们"
    url = f" {policy.product_url}" if policy.product_url else ""
    if any(term in text for term in ("多少钱", "价格", "price", "cost", "how much")):
        return f"感谢关注 {brand}，价格和套餐可以看这里：{url}。你也可以告诉我使用场景，我帮你推荐。".strip()
    if any(term in text for term in ("ship", "shipping", "delivery", "发货", "寄到")):
        return f"感谢关注 {brand}，可以先看这里的购买/配送信息：{url}。如果你发我所在地区，我帮你确认。".strip()
    return f"感谢关注 {brand}，这个点很适合展开聊。{url}".strip()


def _policy_status(text: str, policy: ReplyPolicy) -> tuple[str, str]:
    lowered = text.lower()
    for term in policy.human_review_terms:
        if term.lower() in lowered:
            return "needs_human", f"human_review_terms:{term}"
    return "pending_review", "policy:default_review_required"


def _first_text(raw: RawComment, *keys: str) -> str:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def _author(raw: RawComment) -> str:
    user = raw.get("user")
    if isinstance(user, Mapping):
        return _first_text(user, "nickname", "username", "name", "id")
    return _first_text(raw, "author", "username", "nickname", "user_id")


def _stable_id(*parts: str) -> str:
    source = "\n".join(parts)
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan reviewable social comment replies")
    parser.add_argument("comments", help="Comment export JSON")
    parser.add_argument("--db", required=True, help="SQLite path for comment/reply state")
    parser.add_argument("--brand", default="", help="Brand name to include in draft replies")
    parser.add_argument("--url", default="", help="Product or landing page URL")
    args = parser.parse_args(argv)
    result = plan_reply_workflow(
        args.comments,
        args.db,
        ReplyPolicy(brand_name=args.brand, product_url=args.url),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
