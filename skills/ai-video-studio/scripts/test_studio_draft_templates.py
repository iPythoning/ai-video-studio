import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("MEDIA_DIR", str(Path(tempfile.gettempdir()) / "ai-video-studio-test-media"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio


class StudioDraftTemplatesTest(unittest.TestCase):
    def test_studio_renders_template_draft_from_brief_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "demo.mp4"
            clip.write_bytes(b"video")
            brief_path = root / "brief.json"
            brief_path.write_text(
                json.dumps(
                    {
                        "product_name": "智能保温杯",
                        "brand_name": "ClipForge",
                        "audience": "通勤族",
                        "selling_points": ["12小时保温"],
                        "cta": "现在领取试用",
                        "slug": "mug-campaign",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            old_media_dir = studio.MEDIA_DIR
            studio.MEDIA_DIR = root / "media"
            studio.MEDIA_DIR.mkdir()
            try:
                result = studio.render_template_draft_from_brief(
                    str(brief_path),
                    [str(clip)],
                    backend="capcut",
                    draft_root=str(root / "CapCut Drafts"),
                    template_id="ugc_hook_cta",
                    locales=["zh", "en"],
                    variants=1,
                )
            finally:
                studio.MEDIA_DIR = old_media_dir

            self.assertEqual(result["template_id"], "ugc_hook_cta")
            self.assertEqual(result["variants"], 1)
            self.assertEqual(len(result["draft_plan_paths"]), 2)
            self.assertTrue(all(Path(path).exists() for path in result["draft_plan_paths"]))


if __name__ == "__main__":
    unittest.main()
