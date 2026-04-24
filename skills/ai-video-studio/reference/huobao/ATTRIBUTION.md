# Attribution — Huobao Drama Methodology

The `reference/huobao/` directory contains **prompt-engineering methodology documents** ported from:

- **Project**: [huobao-drama](https://github.com/chatfire-AI/huobao-drama)
- **Author**: chatfire-AI
- **License**: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

## What is ported

Only the SKILL.md methodology / prompt reference files under `huobao-drama/skills/`:

| File | Source |
|------|--------|
| `script_rewriter.md` | `huobao-drama/skills/script_rewriter/SKILL.md` |
| `extractor.md` | `huobao-drama/skills/extractor/SKILL.md` |
| `storyboard_breaker.md` | `huobao-drama/skills/storyboard_breaker/SKILL.md` |
| `voice_assigner.md` | `huobao-drama/skills/voice_assigner/SKILL.md` |
| `grid_prompt_generator/` | `huobao-drama/skills/grid_prompt_generator/` |

No backend/frontend code is copied. The implementation layer (`drama_pipeline.py`)
is original and only *references* these docs as prompt grounding.

## License implications

Because huobao-drama is CC BY-NC-SA 4.0:

1. **Non-commercial**: These ported docs are for non-commercial use. If you embed
   this skill in a paid product, you must either (a) clear commercial licensing
   with chatfire-AI, or (b) replace the prompt-engineering methodology with your
   own equivalents.
2. **Share-alike**: Derivatives of the `reference/huobao/` content must be
   released under the same license. The code in `scripts/` is separate and
   retains `ai-video-studio`'s own license.
3. **Attribution preserved**: This file must stay.
