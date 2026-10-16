from __future__ import annotations

import unittest

from app.services.prompt_composer import (
    compose_canonical_conversion_prompt,
    compose_recipe_prompt,
    compose_tasting_profile_prompt,
)


class PromptComposerTests(unittest.TestCase):
    def test_compose_prompt_contains_required_context(self):
        prompt = compose_recipe_prompt(
            meal_type="lunch_batch",
            instructions="high protein and meal-prep friendly",
            profile={},
            tasting_profile={
                "explicit_dislikes": ["heavy dairy"],
                "hard_avoids_strict": ["peanuts", "sprouts"],
            },
        )

        self.assertIn("Requested meal type:\nlunch_batch", prompt)
        self.assertIn("high protein and meal-prep friendly", prompt)
        self.assertIn('"hard_avoids_strict": [', prompt)
        self.assertIn("## Output schema", prompt)

    def test_compose_canonical_conversion_prompt_contains_allowed_tag_rules(self):
        prompt = compose_canonical_conversion_prompt(
            meal_type="main",
            raw_recipe_text="some raw recipe",
            allowed_tags=["quick", "high-protein"],
        )

        self.assertIn("Tag rules (strict)", prompt)
        self.assertIn("quick, high-protein", prompt)
        self.assertIn("If none fit, return an empty tags list.", prompt)

    def test_compose_tasting_profile_prompt_includes_dynamic_inputs(self):
        prompt = compose_tasting_profile_prompt(
            dislikes=["mushrooms"],
            hard_avoids=["peanuts"],
            current_tasting_profile=None,
            user_recipes=[{"title": "Chicken Pilaf", "meal_type": "main"}],
        )

        self.assertIn('- dislikes: ["mushrooms"]', prompt)
        self.assertIn('- hard_avoids: ["peanuts"]', prompt)
        self.assertIn("Current accepted tasting profile", prompt)
        self.assertIn("null", prompt)
        self.assertIn('"title": "Chicken Pilaf"', prompt)
        self.assertIn('"meal_context_modifiers"', prompt)


if __name__ == "__main__":
    unittest.main()
