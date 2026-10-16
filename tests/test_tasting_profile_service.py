from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from app import create_app
from app.services.tasting_profile_service import generate_tasting_profile_candidate

from tests.fakes import FakeDatabase


class TastingProfileServiceTests(unittest.TestCase):
    def setUp(self):
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["MONGO_URI"] = "mongodb://localhost:27017"
        os.environ["MONGO_DB_NAME"] = "recipelab_test"
        os.environ["LLM_PROVIDER"] = "openai_compatible"
        os.environ["LLM_MODEL"] = "gpt-5.4"

        self.app = create_app()
        self.db = FakeDatabase()

        self.db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": ["peanuts"],
                "likes": ["chicken"],
                "dislikes": ["mushrooms"],
                "notes": "",
                "weights": {},
            }
        )
        self.db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Chicken Pilaf",
                "meal_type": "main",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook"],
                "metadata": {
                    "servings": "2",
                    "prep_time": "10",
                    "cook_time": "25",
                    "rating": "8",
                    "difficulty": "4",
                    "tags": ["quick"],
                },
                "deleted_at": None,
            }
        )

    def tearDown(self):
        self.app.extensions["mongo_client"].close()

    @patch("app.services.tasting_profile_service.LLMAdapter.generate_recipe")
    def test_generate_tasting_profile_candidate_success(self, mock_generate):
        mock_generate.return_value = json.dumps(
            {
                "core_taste_preferences_global": ["Enjoys balanced savory meals"],
                "ingredient_protein_preferences": [
                    "Frequently uses chicken and legumes"
                ],
                "flavour_cuisine_affinities": ["Leans toward Mediterranean profiles"],
                "texture_dish_type_preferences": ["Prefers hearty bowls and stews"],
                "cooking_behaviour_constraints": ["Weeknight-friendly timings"],
                "meal_context_modifiers": {
                    "main": ["Flexible"],
                    "lunch_batch": ["Batch-friendly"],
                    "lunch_single": ["Portable"],
                    "breakfast": ["Light"],
                    "dessert": ["Low evidence"],
                },
                "explicit_dislikes": ["should be replaced"],
                "hard_avoids_strict": ["should be replaced"],
                "inferred_avoidance_signals_red_flags": [
                    "Very spicy dishes rated lower"
                ],
                "ideal_constraints_for_new_suggestions": ["Target 30-45 minute meals"],
                "known_uncertainties_data_gaps": ["Limited dessert data"],
                "evidence_summary": {
                    "recipe_count_used": 999,
                    "high_rating_threshold": 8,
                    "low_rating_threshold": 4,
                    "notes": "Based on current library",
                },
            }
        )

        with self.app.app_context():
            result = generate_tasting_profile_candidate(db=self.db)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 201)
        self.assertEqual(result["status"], "candidate_pending")

        self.assertEqual(len(self.db["tasting_profiles"].docs), 1)
        stored = self.db["tasting_profiles"].docs[0]
        self.assertEqual(stored["profile"]["explicit_dislikes"], ["mushrooms"])
        self.assertEqual(stored["profile"]["hard_avoids_strict"], ["peanuts"])
        self.assertEqual(stored["profile"]["evidence_summary"]["recipe_count_used"], 1)

        self.assertEqual(len(self.db["generation_runs"].docs), 1)
        self.assertEqual(self.db["generation_runs"].docs[0]["status"], "succeeded")

    @patch("app.services.tasting_profile_service.LLMAdapter.generate_recipe")
    def test_generate_tasting_profile_candidate_invalid_json(self, mock_generate):
        mock_generate.return_value = "not-json"

        with self.app.app_context():
            result = generate_tasting_profile_candidate(db=self.db)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 422)
        self.assertIn("not valid JSON", result["error"])
        self.assertEqual(len(self.db["tasting_profiles"].docs), 0)
        self.assertEqual(self.db["generation_runs"].docs[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
