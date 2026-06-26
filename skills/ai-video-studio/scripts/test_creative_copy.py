import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creative_copy


class CreativeCopyTest(unittest.TestCase):
    def test_builds_platform_locale_variant_copy_matrix_without_external_api(self):
        brief = {
            "product_name": "智能保温杯",
            "audience": "通勤族",
            "selling_points": ["12小时保温", "一键开盖"],
            "cta": "现在领取试用",
            "forbidden_words": ["绝对"],
        }

        matrix = creative_copy.build_copy_matrix(
            brief,
            platforms=["tiktok", "shorts"],
            locales=["zh", "en"],
            variants=2,
        )

        self.assertEqual(len(matrix), 8)
        first = matrix[0]
        self.assertEqual(first["platform"], "tiktok")
        self.assertEqual(first["locale"], "zh")
        self.assertEqual(first["variant"], 1)
        self.assertEqual([slot["id"] for slot in first["slots"]], ["hook", "benefit", "cta"])
        self.assertIn("3秒", first["slots"][0]["text"])
        self.assertIn("12小时保温", first["slots"][1]["text"])
        self.assertNotIn("绝对", json.dumps(matrix, ensure_ascii=False))

        shorts_en = creative_copy.find_copy(matrix, platform="shorts", locale="en", variant=2)
        self.assertIn("15 seconds", shorts_en["slots"][0]["text"])
        self.assertIn("one-tap lid", shorts_en["slots"][1]["text"])
        self.assertEqual(shorts_en["slots"][2]["text"], "Claim your trial now")


if __name__ == "__main__":
    unittest.main()
