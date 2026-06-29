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

    def test_can_register_and_select_copy_adapter_by_name(self):
        def custom_adapter(brief, platforms, locales, variants):
            return [
                {
                    "platform": platforms[0],
                    "locale": locales[0],
                    "variant": 1,
                    "slots": [
                        {"id": "hook", "text": f"{brief['product_name']} custom hook"},
                        {"id": "benefit", "text": "custom benefit"},
                        {"id": "cta", "text": "custom cta"},
                    ],
                }
            ]

        creative_copy.register_copy_adapter("unit_test", custom_adapter)
        try:
            matrix = creative_copy.build_copy_matrix(
                {"product_name": "智能保温杯"},
                platforms=["tiktok"],
                locales=["zh"],
                variants=1,
                adapter="unit_test",
            )
        finally:
            creative_copy.unregister_copy_adapter("unit_test")

        self.assertEqual(matrix[0]["source_adapter"], "unit_test")
        self.assertEqual(matrix[0]["slots"][0]["text"], "智能保温杯 custom hook")

    def test_reserved_model_adapters_fail_with_actionable_error_when_unconfigured(self):
        with self.assertRaisesRegex(RuntimeError, "CREATIVE_COPY_ANTHROPIC_COMMAND"):
            creative_copy.build_copy_matrix(
                {"product_name": "智能保温杯"},
                platforms=["tiktok"],
                locales=["zh"],
                variants=1,
                adapter="anthropic",
            )


if __name__ == "__main__":
    unittest.main()
