from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from app import create_app

from tests.fakes import FakeDatabase


class GenerateApiTests(unittest.TestCase):
    def setUp(self):
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["MONGO_URI"] = "mongodb://localhost:27017"
        os.environ["MONGO_DB_NAME"] = "recipelab_test"
        os.environ["LLM_PROVIDER"] = "openai_compatible"
        os.environ["LLM_MODEL"] = "test-model"

        self.fake_db = FakeDatabase()
        self.fake_db["tasting_profiles"].docs.append(
            {
                "_id": "tp1",
                "status": "accepted",
                "is_active": True,
                "profile": {
                    "core_taste_preferences_global": ["balanced savory"],
                    "ingredient_protein_preferences": ["lean proteins"],
                    "flavour_cuisine_affinities": ["mediterranean"],
                    "texture_dish_type_preferences": ["hearty bowls"],
                    "cooking_behaviour_constraints": ["weeknight practical"],
                    "meal_context_modifiers": {
                        "main": ["flexible"],
                        "lunch_batch": ["batch"],
                        "lunch_single": ["portable"],
                        "breakfast": ["light"],
                        "dessert": ["limited"],
                    },
                    "explicit_dislikes": ["mushrooms"],
                    "hard_avoids_strict": ["peanuts"],
                    "inferred_avoidance_signals_red_flags": [],
                    "ideal_constraints_for_new_suggestions": [],
                    "known_uncertainties_data_gaps": [],
                    "evidence_summary": {
                        "recipe_count_used": 1,
                        "high_rating_threshold": 8,
                        "low_rating_threshold": 4,
                        "notes": "",
                    },
                },
            }
        )
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.extensions["mongo_client"].close()

    @patch("app.blueprints.api.routes.get_mongo_db")
    @patch("app.services.generation_service.LLMAdapter.generate_recipe")
    def test_generate_success_persists_suggestion_and_run(
        self, mock_generate, mock_get_mongo_db
    ):
        mock_get_mongo_db.return_value = self.fake_db
        mock_generate.return_value = json.dumps(
            {
                "title": "Spicy Lentil Bowl",
                "meal_type": "main",
                "source": "AI Generated",
                "servings": 2,
                "prep_time": 10,
                "cook_time": 30,
                "rating": 0,
                "difficulty": 4,
                "tags": ["spicy", "lentils"],
                "ingredients": [
                    {"quantity": "1", "unit": "cup", "ingredient": "red lentils"},
                    {"quantity": "2", "unit": "tbsp", "ingredient": "olive oil"},
                ],
                "method": ["Rinse lentils", "Simmer until tender"],
                "notes": ["Freezer friendly"],
            }
        )

        response = self.client.post(
            "/api/generate",
            json={"meal_type": "main", "instructions": "high protein"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["status"], "draft")
        self.assertTrue(payload["validation"]["valid"])

        suggestions = self.fake_db["suggestions"].docs
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["status"], "draft")

        runs = self.fake_db["generation_runs"].docs
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "succeeded")

    @patch("app.blueprints.api.routes.get_mongo_db")
    @patch("app.services.generation_service.LLMAdapter.generate_recipe")
    def test_generate_invalid_output_returns_draft_invalid(
        self, mock_generate, mock_get_mongo_db
    ):
        mock_get_mongo_db.return_value = self.fake_db
        mock_generate.return_value = "this is not json"

        response = self.client.post(
            "/api/generate",
            json={"meal_type": "main", "instructions": "simple"},
        )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertEqual(payload["status"], "draft_invalid")
        self.assertFalse(payload["validation"]["valid"])
        self.assertGreater(len(payload["validation"]["errors"]), 0)

        suggestions = self.fake_db["suggestions"].docs
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["status"], "draft_invalid")

        runs = self.fake_db["generation_runs"].docs
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "failed")

    def test_generate_rejects_invalid_meal_type(self):
        response = self.client.post(
            "/api/generate",
            json={"meal_type": "snack", "instructions": "quick"},
        )

        self.assertEqual(response.status_code, 400)

    @patch("app.blueprints.api.routes.get_mongo_db")
    @patch("app.blueprints.api.routes.generate_recipe_suggestion")
    def test_generate_handles_backend_error(
        self, mock_generate_recipe, mock_get_mongo_db
    ):
        mock_get_mongo_db.return_value = self.fake_db
        mock_generate_recipe.side_effect = RuntimeError("db unavailable")

        response = self.client.post(
            "/api/generate",
            json={"meal_type": "main", "instructions": "quick"},
        )

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertIn("database connection failed", payload["error"])

    @patch("app.blueprints.api.routes.get_mongo_db")
    def test_generate_requires_accepted_tasting_profile(self, mock_get_mongo_db):
        db = FakeDatabase()
        mock_get_mongo_db.return_value = db

        response = self.client.post(
            "/api/generate",
            json={"meal_type": "main", "instructions": "quick"},
        )

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertIn("No accepted tasting profile", payload["error"])


if __name__ == "__main__":
    unittest.main()
