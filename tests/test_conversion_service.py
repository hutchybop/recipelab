from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from app import create_app
from app.services.generation_service import convert_raw_recipe_to_suggestion

from tests.fakes import FakeDatabase


class ConversionServiceTests(unittest.TestCase):
    def setUp(self):
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["MONGO_URI"] = "mongodb://localhost:27017"
        os.environ["MONGO_DB_NAME"] = "recipelab_test"
        os.environ["LLM_PROVIDER"] = "openai_compatible"
        os.environ["LLM_MODEL"] = "gpt-5.4"

        self.app = create_app()
        self.db = FakeDatabase()

    def tearDown(self):
        self.app.extensions["mongo_client"].close()

    @patch("app.services.generation_service.LLMAdapter.generate_recipe")
    def test_convert_raw_recipe_success(self, mock_generate):
        self.db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Tag source",
                "meal_type": "main",
                "source_type": "user",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook"],
                "notes": [],
                "metadata": {"tags": ["soup", "quick"]},
                "deleted_at": None,
            }
        )
        mock_generate.return_value = json.dumps(
            {
                "title": "Imported Chicken Soup",
                "meal_type": "main",
                "source": "Notebook",
                "servings": "2",
                "prep_time": "10",
                "cook_time": "20",
                "rating": "",
                "difficulty": "",
                "tags": ["soup", "invented-tag"],
                "ingredients": [
                    {"quantity": "1", "unit": "cup", "ingredient": "stock"}
                ],
                "method": ["Heat stock"],
                "notes": ["Test note"],
            }
        )

        with self.app.app_context():
            result = convert_raw_recipe_to_suggestion(
                db=self.db,
                meal_type="main",
                raw_recipe_text="Chicken soup raw text",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "draft")
        self.assertEqual(len(self.db["suggestions"].docs), 1)
        self.assertEqual(
            self.db["suggestions"].docs[0]["recipe"]["source_type"], "user"
        )
        self.assertEqual(
            self.db["suggestions"].docs[0]["recipe"]["metadata"]["tags"], ["soup"]
        )

    @patch("app.services.generation_service.LLMAdapter.generate_recipe")
    def test_convert_raw_recipe_invalid_output(self, mock_generate):
        mock_generate.return_value = "not json"

        with self.app.app_context():
            result = convert_raw_recipe_to_suggestion(
                db=self.db,
                meal_type="main",
                raw_recipe_text="Raw text",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "draft_invalid")
        self.assertFalse(result["validation"]["valid"])


if __name__ == "__main__":
    unittest.main()
