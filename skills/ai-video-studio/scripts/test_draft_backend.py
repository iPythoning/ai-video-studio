import tempfile
import unittest
from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_backend


class DraftBackendPlanTest(unittest.TestCase):
    def test_builds_multilingual_capcut_plan_from_storyboard_and_real_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "shot1.mp4"
            voice = root / "voice.zh.mp3"
            clip.write_bytes(b"video")
            voice.write_bytes(b"audio")

            storyboard = {
                "title": "product launch",
                "ratio": "9:16",
                "lang": "zh",
                "template": {"name": "ugc-demo", "platform": "capcut"},
                "shots": [
                    {
                        "caption": "三秒看懂",
                        "narration": "这是第一段中文旁白",
                        "duration": 5,
                        "asset": str(clip),
                        "voiceover": str(voice),
                    }
                ],
                "locales": {
                    "en": {
                        "title": "Product launch",
                        "shots": [{"caption": "Get it in 3 sec", "narration": "English voice-over"}],
                    }
                },
            }

            plan = draft_backend.build_draft_plan(
                storyboard,
                backend="capcut",
                draft_root=str(root / "CapCut Drafts"),
                draft_name="campaign-001",
            )

            self.assertEqual(plan["backend"], "capcut")
            self.assertEqual(plan["draft_name"], "campaign-001")
            self.assertEqual(plan["canvas"], {"width": 1080, "height": 1920})
            self.assertEqual(plan["source_locales"], ["zh", "en"])
            self.assertEqual(plan["operations"][0]["op"], "create_draft")
            self.assertEqual(plan["operations"][1]["op"], "add_video")
            self.assertEqual(plan["operations"][1]["path"], str(clip))
            self.assertEqual(plan["operations"][2]["op"], "add_audio")
            self.assertEqual(plan["operations"][3]["op"], "add_caption")
            self.assertEqual(plan["operations"][-1]["op"], "save")

    def test_expands_template_into_one_draft_plan_per_locale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "shot1.mp4"
            clip.write_bytes(b"video")
            storyboard = {
                "title": "launch",
                "ratio": "9:16",
                "lang": "zh",
                "shots": [{"caption": "中文标题", "duration": 5, "asset": str(clip)}],
                "locales": {
                    "en": {"shots": [{"caption": "English title"}]},
                    "ja": {"shots": [{"caption": "日本語タイトル"}]},
                },
            }

            plans = draft_backend.build_multilingual_draft_plans(
                storyboard,
                backend="jianying",
                draft_root=str(root / "JianyingPro Drafts"),
                draft_name="launch",
            )

            self.assertEqual([plan["locale"] for plan in plans], ["zh", "en", "ja"])
            captions = [
                next(op["text"] for op in plan["operations"] if op["op"] == "add_caption")
                for plan in plans
            ]
            self.assertEqual(captions, ["中文标题", "English title", "日本語タイトル"])
            self.assertEqual(plans[1]["draft_name"], "launch-en")

    def test_executes_capcut_plan_with_pycapcut_when_available(self):
        fake = _fake_editor_module()
        old_module = sys.modules.get("pycapcut")
        sys.modules["pycapcut"] = fake
        try:
            plan = {
                "backend": "capcut",
                "draft_name": "exec-demo",
                "draft_root": "/tmp/CapCut Drafts",
                "canvas": {"width": 1080, "height": 1920},
                "operations": [
                    {"op": "create_draft"},
                    {"op": "add_video", "path": "/tmp/shot.mp4", "start": 0, "duration": 5},
                    {"op": "add_audio", "path": "/tmp/voice.mp3", "start": 0, "duration": 5, "volume": 0.8},
                    {"op": "add_caption", "text": "Hello", "start": 0, "duration": 5},
                    {"op": "save"},
                ],
            }

            result = draft_backend.execute_draft_plan(plan)

            self.assertEqual(result["status"], "executed")
            self.assertEqual(result["backend"], "capcut")
            self.assertEqual(fake.calls[0], ("folder", "/tmp/CapCut Drafts"))
            self.assertEqual(fake.calls[1], ("create", "exec-demo", 1080, 1920, True))
            self.assertIn(("track", "video"), fake.calls)
            self.assertIn(("track", "audio"), fake.calls)
            self.assertIn(("track", "text"), fake.calls)
            self.assertIn(("segment", "VideoSegment"), fake.calls)
            self.assertIn(("segment", "AudioSegment"), fake.calls)
            self.assertIn(("segment", "TextSegment"), fake.calls)
            self.assertIn(("save",), fake.calls)
        finally:
            if old_module is None:
                sys.modules.pop("pycapcut", None)
            else:
                sys.modules["pycapcut"] = old_module


def _fake_editor_module():
    fake = types.ModuleType("pycapcut")
    fake.calls = []

    class TrackType:
        video = "video"
        audio = "audio"
        text = "text"

    class DraftFolder:
        def __init__(self, root):
            fake.calls.append(("folder", root))

        def create_draft(self, name, width, height, allow_replace=False):
            fake.calls.append(("create", name, width, height, allow_replace))
            return Script()

    class Script:
        def add_track(self, track):
            fake.calls.append(("track", track))
            return self

        def add_segment(self, segment):
            fake.calls.append(("segment", type(segment).__name__))
            return self

        def save(self):
            fake.calls.append(("save",))

    class VideoSegment:
        def __init__(self, *_args, **_kwargs):
            pass

    class AudioSegment:
        def __init__(self, *_args, **_kwargs):
            pass

    class TextSegment:
        def __init__(self, *_args, **_kwargs):
            pass

    class TextStyle:
        def __init__(self, *_args, **_kwargs):
            pass

    class ClipSettings:
        def __init__(self, *_args, **_kwargs):
            pass

    fake.TrackType = TrackType
    fake.DraftFolder = DraftFolder
    fake.VideoSegment = VideoSegment
    fake.AudioSegment = AudioSegment
    fake.TextSegment = TextSegment
    fake.TextStyle = TextStyle
    fake.ClipSettings = ClipSettings
    fake.trange = lambda start, duration: {"start": start, "duration": duration}
    return fake


if __name__ == "__main__":
    unittest.main()
