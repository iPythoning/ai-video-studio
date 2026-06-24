import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


class ServerDraftTemplatesTest(unittest.TestCase):
    def test_server_renders_template_drafts_without_generation_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "demo.mp4"
            clip.write_bytes(b"video")
            server = _load_server(root / "media")
            req = server.TemplateDraftRequest(
                brief={
                    "product_name": "智能保温杯",
                    "brand_name": "ClipForge",
                    "audience": "通勤族",
                    "selling_points": ["12小时保温"],
                    "cta": "现在领取试用",
                    "slug": "mug-campaign",
                },
                assets=[str(clip)],
                backend="jianying",
                draft_root=str(root / "Jianying Drafts"),
                template_id="ugc_hook_cta",
                locales=["zh", "en"],
                variants=2,
            )

            result = server._render_template_draft(req)

            self.assertEqual(result["renderer"], "jianying_draft")
            self.assertEqual(result["template_id"], "ugc_hook_cta")
            self.assertEqual(result["variants"], 2)
            self.assertEqual(result["locales"], ["zh", "en"])
            self.assertEqual(len(result["draft_plan_paths"]), 4)
            self.assertTrue(all(Path(path).exists() for path in result["draft_plan_paths"]))


def _load_server(media_dir: Path):
    media_dir.mkdir(parents=True)
    os.environ["MEDIA_DIR"] = str(media_dir)
    for name in ("server", "studio"):
        sys.modules.pop(name, None)
    return importlib.import_module("server")


if __name__ == "__main__":
    unittest.main()
