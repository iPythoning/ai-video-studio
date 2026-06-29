import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_templates


class DraftTemplatesTest(unittest.TestCase):
    def test_builds_multilingual_template_storyboards_from_brief_and_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clips = [root / "shot1.mp4", root / "shot2.mp4"]
            for clip in clips:
                clip.write_bytes(b"video")
            brief = {
                "product_name": "智能保温杯",
                "brand_name": "ClipForge",
                "audience": "通勤族",
                "selling_points": ["12小时保温", "一键开盖"],
                "cta": "现在领取试用",
                "forbidden_words": ["绝对"],
            }

            storyboards = draft_templates.build_template_storyboards(
                brief,
                [str(path) for path in clips],
                template_id="ugc_hook_cta",
                locales=["zh", "en"],
                variants=3,
            )

            self.assertEqual(len(storyboards), 3)
            first = storyboards[0]
            self.assertEqual(first["renderer"], "capcut_draft")
            self.assertEqual(first["ratio"], "9:16")
            self.assertEqual(first["lang"], "zh")
            self.assertEqual(first["template"]["id"], "ugc_hook_cta")
            self.assertEqual(first["template"]["caption_position"], "lower-third-safe")
            self.assertEqual(first["draft_name"], "smart-mug-v1")
            self.assertEqual([shot["asset"] for shot in first["shots"]], [str(clips[0]), str(clips[1]), str(clips[0])])
            self.assertIn("智能保温杯", first["shots"][0]["caption"])
            self.assertNotIn("绝对", json.dumps(first, ensure_ascii=False))
            self.assertEqual(first["locales"]["en"]["shots"][0]["caption"], "Stop scrolling: Smart Mug for commuters")
            self.assertEqual(storyboards[2]["draft_name"], "smart-mug-v3")

    def test_renders_template_package_into_variant_and_locale_draft_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "demo.mp4"
            clip.write_bytes(b"video")
            brief = {
                "product_name": "智能保温杯",
                "brand_name": "ClipForge",
                "audience": "通勤族",
                "selling_points": ["12小时保温"],
                "cta": "现在领取试用",
                "slug": "mug-campaign",
            }

            result = draft_templates.render_template_draft_package(
                brief,
                [str(clip)],
                backend="capcut",
                draft_root=str(root / "CapCut Drafts"),
                output_dir=root / "out",
                template_id="ugc_hook_cta",
                locales=["zh", "en"],
                variants=2,
            )

            self.assertEqual(result["template_id"], "ugc_hook_cta")
            self.assertEqual(result["variants"], 2)
            self.assertEqual(result["locales"], ["zh", "en"])
            self.assertEqual(len(result["draft_plan_paths"]), 4)
            for path in result["draft_plan_paths"]:
                self.assertTrue(Path(path).exists())
            zh_plan = json.loads(Path(result["draft_plan_paths"][0]).read_text(encoding="utf-8"))
            en_plan = json.loads(Path(result["draft_plan_paths"][1]).read_text(encoding="utf-8"))
            self.assertEqual(zh_plan["locale"], "zh")
            self.assertEqual(en_plan["locale"], "en")
            self.assertEqual(zh_plan["operations"][1]["path"], str(clip))

    def test_renders_platform_locale_variant_matrix_with_safe_zone_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "demo.mp4"
            clip.write_bytes(b"video")
            brief = {
                "product_name": "智能保温杯",
                "audience": "通勤族",
                "selling_points": ["12小时保温"],
                "cta": "现在领取试用",
                "slug": "mug-campaign",
            }

            result = draft_templates.render_template_draft_package(
                brief,
                [str(clip)],
                backend="capcut",
                draft_root=str(root / "CapCut Drafts"),
                output_dir=root / "out",
                template_id="ugc_hook_cta",
                locales=["zh", "en"],
                platforms=["tiktok", "shorts"],
                variants=2,
            )

            self.assertEqual(result["platforms"], ["tiktok", "shorts"])
            self.assertEqual(len(result["outputs"]), 4)
            self.assertEqual(len(result["draft_plan_paths"]), 8)
            first_plan = json.loads(Path(result["draft_plan_paths"][0]).read_text(encoding="utf-8"))
            shorts_plan = json.loads(Path(result["draft_plan_paths"][4]).read_text(encoding="utf-8"))
            self.assertEqual(first_plan["platform"], "tiktok")
            self.assertEqual(first_plan["template"]["safe_zones"]["bottom"], 340)
            self.assertEqual(first_plan["operations"][0]["platform"], "tiktok")
            self.assertEqual(shorts_plan["platform"], "shorts")
            self.assertEqual(shorts_plan["template"]["safe_zones"]["bottom"], 300)

    def test_can_use_local_creative_copy_matrix_for_platform_specific_captions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "demo.mp4"
            clip.write_bytes(b"video")
            brief = {
                "product_name": "智能保温杯",
                "audience": "通勤族",
                "selling_points": ["12小时保温", "一键开盖"],
                "cta": "现在领取试用",
                "slug": "mug-campaign",
            }

            result = draft_templates.render_template_draft_package(
                brief,
                [str(clip)],
                backend="capcut",
                draft_root=str(root / "CapCut Drafts"),
                output_dir=root / "out",
                template_id="ugc_hook_cta",
                locales=["zh", "en"],
                platforms=["tiktok", "shorts"],
                variants=2,
                creative_copy_mode="local_rules",
            )

            tiktok_zh = json.loads(Path(result["draft_plan_paths"][0]).read_text(encoding="utf-8"))
            shorts_en = json.loads(Path(result["draft_plan_paths"][-1]).read_text(encoding="utf-8"))
            tiktok_caption = next(op["text"] for op in tiktok_zh["operations"] if op["op"] == "add_caption")
            shorts_caption = next(op["text"] for op in shorts_en["operations"] if op["op"] == "add_caption")
            self.assertEqual(result["copy_source"], "local_rules")
            self.assertIn("3秒", tiktok_caption)
            self.assertIn("15 seconds", shorts_caption)


if __name__ == "__main__":
    unittest.main()
