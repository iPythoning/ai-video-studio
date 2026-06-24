import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


class ServerSocialRepliesTest(unittest.TestCase):
    def test_server_plans_social_reply_jobs_without_llm_or_sender(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = _load_server(Path(tmp) / "media")
            req = server.SocialReplyRequest(
                comments=[
                    {
                        "platform": "youtube",
                        "comment_id": "yt-1",
                        "video_id": "short-1",
                        "author": "lee",
                        "text": "How much is this?",
                    }
                ],
                db_path=str(Path(tmp) / "social.sqlite"),
                brand_name="ClipForge",
                product_url="https://example.com/buy",
            )

            result = server._plan_social_replies(req)

            self.assertEqual(result["ingest"], {"inserted": 1, "duplicates": 0, "skipped": 0})
            self.assertEqual(result["planned"], 1)
            self.assertEqual(result["jobs"][0]["status"], "pending_review")
            self.assertIn("ClipForge", result["jobs"][0]["draft_reply"])
            self.assertEqual(result["db_path"], str(Path(tmp) / "social.sqlite"))


def _load_server(media_dir: Path):
    media_dir.mkdir(parents=True)
    os.environ["MEDIA_DIR"] = str(media_dir)
    for name in ("server", "studio"):
        sys.modules.pop(name, None)
    return importlib.import_module("server")


if __name__ == "__main__":
    unittest.main()
