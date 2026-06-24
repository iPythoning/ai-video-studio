import tempfile
import unittest
from pathlib import Path
import sys
import json
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parent))
import social_replies


class SocialRepliesTest(unittest.TestCase):
    def test_comment_store_context_manager_closes_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            with social_replies.CommentStore(Path(tmp) / "comments.sqlite") as store:
                store.ingest([])

            with self.assertRaises(sqlite3.ProgrammingError):
                store.list_reply_jobs()

    def test_ingests_comments_once_and_creates_review_reply_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            with social_replies.CommentStore(Path(tmp) / "comments.sqlite") as store:
                raw = [
                    {
                        "platform": "douyin",
                        "comment_id": "c1",
                        "post_id": "v1",
                        "author": "alice",
                        "text": "这个多少钱？",
                        "created_at": "2026-06-24T10:00:00Z",
                    },
                    {
                        "platform": "douyin",
                        "comment_id": "c1",
                        "post_id": "v1",
                        "author": "alice",
                        "text": "这个多少钱？",
                        "created_at": "2026-06-24T10:00:00Z",
                    },
                    {
                        "platform": "instagram",
                        "id": "c1",
                        "media_id": "reel-7",
                        "username": "bob",
                        "text": "Do you ship to the US?",
                    },
                ]

                summary = store.ingest(raw)
                jobs = store.plan_reply_jobs(
                    social_replies.ReplyPolicy(brand_name="ClipForge", product_url="https://example.com"),
                )

                self.assertEqual(summary, {"inserted": 2, "duplicates": 1, "skipped": 0})
                self.assertEqual(len(jobs), 2)
                self.assertEqual({job["platform"] for job in jobs}, {"douyin", "instagram"})
                self.assertTrue(all(job["status"] == "pending_review" for job in jobs))
                self.assertIn("ClipForge", jobs[0]["draft_reply"])
                self.assertEqual(store.plan_reply_jobs(social_replies.ReplyPolicy()), [])

    def test_flags_sensitive_comments_for_human_review_without_draft_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            with social_replies.CommentStore(Path(tmp) / "comments.sqlite") as store:
                store.ingest(
                    [
                        {
                            "platform": "youtube",
                            "comment_id": "danger",
                            "video_id": "short-1",
                            "author": "casey",
                            "text": "退款不到账，准备投诉",
                        }
                    ]
                )

                jobs = store.plan_reply_jobs(
                    social_replies.ReplyPolicy(human_review_terms=("退款", "投诉"))
                )

                self.assertEqual(len(jobs), 1)
                self.assertEqual(jobs[0]["status"], "needs_human")
                self.assertEqual(jobs[0]["draft_reply"], "")
                self.assertIn("human_review_terms", jobs[0]["reason"])

    def test_plan_reply_workflow_reads_export_file_and_persists_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_path = root / "comments.json"
            db_path = root / "social.sqlite"
            export_path.write_text(
                json.dumps(
                    [
                        {
                            "platform": "tiktok",
                            "id": "tk-1",
                            "video_id": "video-1",
                            "username": "morgan",
                            "text": "How much is this?",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            result = social_replies.plan_reply_workflow(
                export_path,
                db_path,
                social_replies.ReplyPolicy(brand_name="ClipForge", product_url="https://example.com/buy"),
            )
            self.assertEqual(result["ingest"], {"inserted": 1, "duplicates": 0, "skipped": 0})
            self.assertEqual(result["planned"], 1)
            with social_replies.CommentStore(db_path) as store:
                self.assertEqual(store.list_reply_jobs()[0]["platform"], "tiktok")


if __name__ == "__main__":
    unittest.main()
