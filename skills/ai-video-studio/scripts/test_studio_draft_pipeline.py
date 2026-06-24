import json
import os
import sys
import tempfile
import unittest
import types
from pathlib import Path

os.environ.setdefault("MEDIA_DIR", str(Path(tempfile.gettempdir()) / "ai-video-studio-test-media"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio


class StudioDraftPipelineTest(unittest.TestCase):
    def test_pipeline_uses_existing_shot_assets_for_capcut_draft_without_seedance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root / "real-shoot.mp4"
            clip.write_bytes(b"video")
            storyboard = {
                "title": "real asset draft",
                "ratio": "9:16",
                "renderer": "capcut_draft",
                "tts": False,
                "draft_root": str(root / "CapCut Drafts"),
                "shots": [
                    {
                        "asset": str(clip),
                        "caption": "真实素材",
                        "duration": 5,
                    }
                ],
            }
            storyboard_path = root / "storyboard.json"
            storyboard_path.write_text(json.dumps(storyboard), encoding="utf-8")

            def fail_seedance(*_args, **_kwargs):
                raise AssertionError("Seedance should not run for existing shot assets")

            old_submit = studio.seedance_submit
            old_media_dir = studio.MEDIA_DIR
            studio.seedance_submit = fail_seedance
            studio.MEDIA_DIR = root / "media"
            studio.MEDIA_DIR.mkdir()
            try:
                result = studio.run_pipeline(str(storyboard_path))
            finally:
                studio.seedance_submit = old_submit
                studio.MEDIA_DIR = old_media_dir

            self.assertEqual(result["renderer"], "capcut_draft")
            plan_path = Path(result["draft_plan_path"])
            self.assertTrue(plan_path.exists())
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["operations"][1]["op"], "add_video")
            self.assertEqual(plan["operations"][1]["path"], str(clip))

    def test_pipeline_can_execute_capcut_draft_with_optional_editor_module(self):
        fake = _fake_editor_module()
        old_module = sys.modules.get("pycapcut")
        sys.modules["pycapcut"] = fake
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                clip = root / "real-shoot.mp4"
                clip.write_bytes(b"video")
                storyboard = {
                    "title": "execute draft",
                    "ratio": "9:16",
                    "renderer": "capcut_draft",
                    "draft_execute": True,
                    "tts": False,
                    "draft_root": str(root / "CapCut Drafts"),
                    "shots": [{"asset": str(clip), "caption": "执行草稿", "duration": 5}],
                }
                storyboard_path = root / "storyboard.json"
                storyboard_path.write_text(json.dumps(storyboard), encoding="utf-8")

                old_media_dir = studio.MEDIA_DIR
                studio.MEDIA_DIR = root / "media"
                studio.MEDIA_DIR.mkdir()
                try:
                    result = studio.run_pipeline(str(storyboard_path))
                finally:
                    studio.MEDIA_DIR = old_media_dir

                self.assertEqual(result["execution"][0]["status"], "executed")
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
