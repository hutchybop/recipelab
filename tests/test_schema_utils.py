from __future__ import annotations

import unittest

from app.services.schema_utils import (
    normalize_generation_run_document,
    normalize_preference_document,
    normalize_recipe_document,
    normalize_suggestion_document,
)


class SchemaUtilsTests(unittest.TestCase):
    def test_normalize_recipe_document_success(self):
        recipe = normalize_recipe_document(
            {
                "title": "Chicken Pilaf",
                "meal_type": "main",
                "ingredients": ["300 g chicken breast"],
                "method": ["Cook it"],
                "tags": ["dinner", "chicken"],
            }
        )

        self.assertEqual(recipe["title"], "Chicken Pilaf")
        self.assertEqual(recipe["ingredients"][0]["quantity"], "300")
        self.assertEqual(recipe["ingredients"][0]["unit"], "g")
        self.assertEqual(recipe["ingredients"][0]["ingredient"], "chicken breast")
        self.assertEqual(recipe["metadata"]["tags"], ["dinner", "chicken"])

    def test_normalize_recipe_document_invalid_meal_type(self):
        with self.assertRaises(ValueError):
            normalize_recipe_document(
                {
                    "title": "Invalid",
                    "meal_type": "snack",
                    "ingredients": ["1 apple"],
                    "method": ["Eat"],
                }
            )

    def test_normalize_suggestion_document_defaults_status(self):
        suggestion = normalize_suggestion_document(
            {"title": "S1", "meal_type": "dessert"}
        )
        self.assertEqual(suggestion["status"], "draft")

    def test_normalize_preference_document(self):
        profile = normalize_preference_document(
            {"profile_name": "default", "hard_avoids": ["peanuts"]}
        )
        self.assertTrue(profile["active"])
        self.assertEqual(profile["hard_avoids"], ["peanuts"])

    def test_normalize_generation_run_document(self):
        run = normalize_generation_run_document(
            {"meal_type": "main", "model": "gpt-test"}
        )
        self.assertEqual(run["status"], "started")


if __name__ == "__main__":
    unittest.main()
