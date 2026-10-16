from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import create_app

from tests.fakes import FakeDatabase


class WebRoutesTests(unittest.TestCase):
    def setUp(self):
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["MONGO_URI"] = "mongodb://localhost:27017"
        os.environ["MONGO_DB_NAME"] = "recipelab_test"
        os.environ["LLM_PROVIDER"] = "openai_compatible"
        os.environ["LLM_MODEL"] = "gpt-5.4"
        os.environ["LLM_ALLOWED_MODELS"] = "gpt-5.4,deepseek-v4.1-flash"

        self.app = create_app()
        self.client = self.app.test_client()
        self.fake_db = FakeDatabase()

    def tearDown(self):
        self.app.extensions["mongo_client"].close()

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_dashboard_renders(self, mock_db):
        mock_db.return_value = self.fake_db
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recipe Dashboard", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_generate_page_renders(self, mock_db):
        mock_db.return_value = self.fake_db
        response = self.client.get("/generate")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Generate a Recipe", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_import_page_renders(self, mock_db):
        mock_db.return_value = self.fake_db
        response = self.client.get("/import")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Import Raw Recipe", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_settings_page_renders(self, mock_db):
        mock_db.return_value = self.fake_db
        response = self.client.get("/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Runtime Settings", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_settings_post_persists_model(self, mock_db):
        mock_db.return_value = self.fake_db
        response = self.client.post("/settings", data={"model": "deepseek-v4.1-flash"})
        self.assertEqual(response.status_code, 302)

        settings_docs = self.fake_db["runtime_settings"].docs
        self.assertEqual(len(settings_docs), 1)
        self.assertEqual(settings_docs[0]["value"], "deepseek-v4.1-flash")

    @patch("app.blueprints.web.routes.get_mongo_db")
    @patch("app.blueprints.web.routes.generate_recipe_suggestion")
    def test_generate_post_redirects_to_suggestion_detail(self, mock_generate, mock_db):
        mock_db.return_value = self.fake_db
        mock_generate.return_value = {
            "ok": True,
            "status": "draft",
            "suggestion_id": "s1",
        }

        response = self.client.post(
            "/generate",
            data={
                "meal_type": "main",
                "instructions": "quick dinner",
                "model": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/suggestions/s1", response.location)

    @patch("app.blueprints.web.routes.get_mongo_db")
    @patch("app.blueprints.web.routes.convert_raw_recipe_to_suggestion")
    def test_import_post_redirects_to_suggestion_detail(self, mock_convert, mock_db):
        mock_db.return_value = self.fake_db
        mock_convert.return_value = {
            "ok": True,
            "status": "draft",
            "suggestion_id": "s2",
        }

        response = self.client.post(
            "/import",
            data={
                "meal_type": "main",
                "raw_recipe_text": "Title\nIngredients\nMethod",
                "model": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/suggestions/s2", response.location)

    @patch("app.blueprints.web.routes.get_mongo_db")
    @patch("app.blueprints.web.routes.generate_recipe_suggestion")
    def test_generate_post_handles_backend_error(self, mock_generate, mock_db):
        mock_db.return_value = self.fake_db
        mock_generate.side_effect = RuntimeError("db unavailable")

        response = self.client.post(
            "/generate",
            data={
                "meal_type": "main",
                "instructions": "quick dinner",
                "model": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/generate", response.location)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_suggestions_page_renders(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["suggestions"].docs.append(
            {
                "_id": "s1",
                "title": "Test Suggestion",
                "meal_type": "main",
                "status": "draft",
                "recipe": {"ingredients": [], "method": [], "metadata": {}},
                "validation": {"valid": True, "errors": []},
                "created_at": 1,
            }
        )

        response = self.client.get("/suggestions")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Suggestion", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_page_renders(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": ["peanuts"],
                "likes": ["chicken"],
                "dislikes": [],
                "notes": "",
                "weights": {},
            }
        )

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tasting Profile", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_page_shows_active_and_candidate_profiles(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "dislikes": [],
                "weights": {},
            }
        )
        self.fake_db["tasting_profiles"].docs.extend(
            [
                {
                    "_id": "tp-active",
                    "status": "accepted",
                    "is_active": True,
                    "profile": {"core_taste_preferences_global": ["Balanced savory"]},
                    "review": {
                        "decision": "accepted",
                        "decision_note": "",
                        "decided_at": 2,
                    },
                    "accepted_at": 2,
                    "created_at": 1,
                },
                {
                    "_id": "tp-candidate",
                    "status": "candidate_pending",
                    "is_active": False,
                    "profile": {"core_taste_preferences_global": ["Batch-friendly"]},
                    "review": {
                        "decision": "pending",
                        "decision_note": "",
                        "decided_at": None,
                    },
                    "created_at": 3,
                },
            ]
        )

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Latest Candidate", response.data)
        self.assertIn(b"Active Accepted Tasting Profile", response.data)
        self.assertIn(b"Accept Candidate", response.data)
        self.assertIn(b"Balanced savory", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_page_shows_staleness_warning_for_active_profile(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "dislikes": [],
                "weights": {},
            }
        )
        self.fake_db["recipes"].docs.extend(
            [
                {
                    "_id": "r1",
                    "title": "R1",
                    "meal_type": "main",
                    "created_at": 1,
                    "deleted_at": None,
                },
                {
                    "_id": "r2",
                    "title": "R2",
                    "meal_type": "main",
                    "created_at": 2,
                    "deleted_at": None,
                },
            ]
        )
        self.fake_db["tasting_profiles"].docs.append(
            {
                "_id": "tp-active",
                "status": "accepted",
                "is_active": True,
                "profile": {"core_taste_preferences_global": ["Balanced savory"]},
                "input_snapshot": {"recipe_ids": ["r1"], "recipe_count": 1},
                "review": {
                    "decision": "accepted",
                    "decision_note": "",
                    "decided_at": 2,
                },
                "accepted_at": 2,
                "created_at": 1,
            }
        )

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"may be stale", response.data)
        self.assertIn(b"1 recipe(s) added", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_page_shows_candidate_diff_summary(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "dislikes": [],
                "weights": {},
            }
        )
        self.fake_db["tasting_profiles"].docs.extend(
            [
                {
                    "_id": "tp-active",
                    "status": "accepted",
                    "is_active": True,
                    "profile": {
                        "core_taste_preferences_global": ["Balanced savory"],
                        "ingredient_protein_preferences": ["Chicken"],
                    },
                    "review": {
                        "decision": "accepted",
                        "decision_note": "",
                        "decided_at": 2,
                    },
                    "accepted_at": 2,
                    "created_at": 1,
                },
                {
                    "_id": "tp-candidate",
                    "status": "candidate_pending",
                    "is_active": False,
                    "profile": {
                        "core_taste_preferences_global": ["Balanced savory"],
                        "ingredient_protein_preferences": ["Fish"],
                    },
                    "review": {
                        "decision": "pending",
                        "decision_note": "",
                        "decided_at": None,
                    },
                    "created_at": 3,
                },
            ]
        )

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Candidate differs from active profile", response.data)
        self.assertIn(b"ingredient_protein_preferences", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_page_saves_only_dislikes_and_hard_avoids(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "likes": ["beans"],
                "dislikes": ["mushrooms"],
                "notes": "legacy",
                "weights": {},
            }
        )

        response = self.client.post(
            "/profile",
            data={
                "action": "save_profile",
                "dislikes": "mushrooms\nonions",
                "hard_avoids": "peanuts",
            },
        )

        self.assertEqual(response.status_code, 302)
        active = self.fake_db["preferences"].docs[0]
        self.assertEqual(active["dislikes"], ["mushrooms", "onions"])
        self.assertEqual(active["hard_avoids"], ["peanuts"])
        self.assertEqual(active["likes"], [])
        self.assertEqual(active["notes"], "")

    @patch("app.blueprints.web.routes.get_mongo_db")
    @patch("app.blueprints.web.routes.generate_tasting_profile_candidate")
    def test_profile_page_generates_tasting_profile_candidate(
        self, mock_generate_profile, mock_db
    ):
        mock_db.return_value = self.fake_db
        mock_generate_profile.return_value = {
            "ok": True,
            "status_code": 201,
            "candidate_id": "tp1",
            "status": "candidate_pending",
        }

        response = self.client.post(
            "/profile", data={"action": "generate_tasting_profile"}
        )
        self.assertEqual(response.status_code, 302)
        mock_generate_profile.assert_called_once()

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_accept_and_reject_tasting_profile_routes(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["tasting_profiles"].docs.append(
            {
                "_id": "tp1",
                "status": "candidate_pending",
                "is_active": False,
                "profile": {"core_taste_preferences_global": ["Balanced savory"]},
                "review": {
                    "decision": "pending",
                    "decision_note": "",
                    "decided_at": None,
                },
            }
        )

        response = self.client.post("/profile/tasting-profiles/tp1/accept")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.fake_db["tasting_profiles"].docs[0]["status"], "accepted")
        self.assertTrue(self.fake_db["tasting_profiles"].docs[0]["is_active"])

        self.fake_db["tasting_profiles"].docs.append(
            {
                "_id": "tp2",
                "status": "candidate_pending",
                "is_active": False,
                "profile": {"core_taste_preferences_global": ["Batch-friendly"]},
                "review": {
                    "decision": "pending",
                    "decision_note": "",
                    "decided_at": None,
                },
            }
        )
        response = self.client.post("/profile/tasting-profiles/tp2/reject")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.fake_db["tasting_profiles"].docs[1]["status"], "rejected")
        self.assertFalse(self.fake_db["tasting_profiles"].docs[1]["is_active"])

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_recipe_detail_renders_without_feedback_section(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Test Recipe",
                "meal_type": "main",
                "source_type": "user",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook rice"],
                "notes": [],
                "metadata": {"tags": []},
                "deleted_at": None,
            }
        )

        response = self.client.get("/recipes/r1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Recipe", response.data)
        self.assertNotIn(b"Current feedback", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_recipes_page_renders_without_feedback_badges(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.extend(
            [
                {
                    "_id": "r1",
                    "title": "Recipe One",
                    "meal_type": "main",
                    "created_at": 2,
                },
                {
                    "_id": "r2",
                    "title": "Recipe Two",
                    "meal_type": "main",
                    "created_at": 1,
                },
            ]
        )

        response = self.client.get("/recipes")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recipe One", response.data)
        self.assertIn(b"Recipe Two", response.data)
        self.assertNotIn(b"Liked", response.data)
        self.assertNotIn(b"Disliked", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_suggestion_detail_renders_without_feedback_section(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["suggestions"].docs.append(
            {
                "_id": "s1",
                "title": "Test Suggestion",
                "meal_type": "main",
                "status": "draft",
                "recipe": {"ingredients": [], "method": [], "metadata": {}},
                "validation": {"valid": True, "errors": []},
                "created_at": 1,
            }
        )

        response = self.client.get("/suggestions/s1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Suggestion", response.data)
        self.assertNotIn(b"Current feedback", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_feedback_routes_are_removed(self, mock_db):
        mock_db.return_value = self.fake_db
        response = self.client.post(
            "/feedback",
            data={
                "target_type": "recipe",
                "target_id": "r1",
                "signal": "liked",
                "notes": "Great",
                "return_to": "/recipes",
            },
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            "/feedback/clear-reaction",
            data={"target_type": "recipe", "target_id": "r1"},
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            "/feedback/clear-note",
            data={"target_type": "recipe", "target_id": "r1"},
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post("/profile/suggestions/u1/apply")
        self.assertEqual(response.status_code, 404)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_accept_suggestion_saves_recipe(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["suggestions"].docs.append(
            {
                "_id": "s1",
                "title": "Test Suggestion",
                "meal_type": "main",
                "status": "draft",
                "recipe": {
                    "title": "Test Suggestion",
                    "meal_type": "main",
                    "source_type": "ai",
                    "metadata": {
                        "source": "AI Generated",
                        "servings": "2",
                        "prep_time": "10",
                        "cook_time": "20",
                        "rating": "",
                        "difficulty": "",
                        "tags": ["quick"],
                    },
                    "ingredients": [
                        {"quantity": "1", "unit": "cup", "ingredient": "rice"}
                    ],
                    "method": ["Cook rice"],
                    "notes": [],
                },
                "validation": {"valid": True, "errors": []},
                "created_at": 1,
            }
        )

        response = self.client.post("/suggestions/s1/accept")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/recipes/", response.location)

        self.assertEqual(len(self.fake_db["recipes"].docs), 1)
        self.assertEqual(self.fake_db["suggestions"].docs[0]["status"], "accepted")

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_edit_suggestion_updates_and_sets_draft(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["suggestions"].docs.append(
            {
                "_id": "s-edit",
                "title": "Draft Suggestion",
                "meal_type": "main",
                "status": "draft_invalid",
                "recipe": {
                    "title": "Draft Suggestion",
                    "meal_type": "main",
                    "source_type": "user",
                    "metadata": {
                        "source": "",
                        "servings": "",
                        "prep_time": "",
                        "cook_time": "",
                        "rating": "",
                        "difficulty": "",
                        "tags": [],
                    },
                    "ingredients": [
                        {"quantity": "1", "unit": "cup", "ingredient": "rice"}
                    ],
                    "method": ["Cook rice"],
                    "notes": [],
                },
                "validation": {"valid": False, "errors": ["bad format"]},
                "created_at": 1,
            }
        )

        response = self.client.post(
            "/suggestions/s-edit/edit",
            data={
                "title": "Edited Suggestion",
                "meal_type": "main",
                "source_type": "user",
                "source": "",
                "servings": "2",
                "prep_time": "5",
                "cook_time": "10",
                "difficulty": "",
                "rating": "",
                "tags": "quick",
                "ingredients": "1 cup rice",
                "method": "Cook rice",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/suggestions/s-edit", response.location)
        self.assertEqual(self.fake_db["suggestions"].docs[0]["status"], "draft")
        self.assertEqual(
            self.fake_db["suggestions"].docs[0]["title"], "Edited Suggestion"
        )

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_edit_suggestion_merges_selected_and_new_tags(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Tag Source",
                "meal_type": "main",
                "source_type": "user",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook"],
                "notes": [],
                "metadata": {"tags": ["quick", "batch"]},
                "deleted_at": None,
            }
        )
        self.fake_db["suggestions"].docs.append(
            {
                "_id": "s-edit",
                "title": "Draft Suggestion",
                "meal_type": "main",
                "status": "draft_invalid",
                "recipe": {
                    "title": "Draft Suggestion",
                    "meal_type": "main",
                    "source_type": "user",
                    "metadata": {
                        "source": "",
                        "servings": "",
                        "prep_time": "",
                        "cook_time": "",
                        "rating": "",
                        "difficulty": "",
                        "tags": ["quick"],
                    },
                    "ingredients": [
                        {"quantity": "1", "unit": "cup", "ingredient": "rice"}
                    ],
                    "method": ["Cook rice"],
                    "notes": [],
                },
                "validation": {"valid": False, "errors": ["bad format"]},
                "created_at": 1,
            }
        )

        response = self.client.post(
            "/suggestions/s-edit/edit",
            data={
                "title": "Edited Suggestion",
                "meal_type": "main",
                "source_type": "user",
                "source": "",
                "servings": "2",
                "prep_time": "5",
                "cook_time": "10",
                "difficulty": "",
                "rating": "",
                "tags_selected": ["quick", "batch"],
                "new_tags": "High-Protein",
                "ingredients": "1 cup rice",
                "method": "Cook rice",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/suggestions/s-edit", response.location)
        self.assertEqual(
            self.fake_db["suggestions"].docs[0]["recipe"]["metadata"]["tags"],
            ["quick", "batch", "high-protein"],
        )

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_edit_recipe_updates_title(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Old Title",
                "meal_type": "main",
                "source_type": "user",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook rice"],
                "notes": [],
                "metadata": {
                    "source": "",
                    "servings": "1",
                    "prep_time": "5",
                    "cook_time": "10",
                    "rating": "",
                    "difficulty": "",
                    "tags": [],
                },
                "deleted_at": None,
            }
        )

        response = self.client.post(
            "/recipes/r1/edit",
            data={
                "title": "New Title",
                "meal_type": "main",
                "source_type": "user",
                "source": "",
                "servings": "1",
                "prep_time": "5",
                "cook_time": "10",
                "difficulty": "",
                "rating": "",
                "tags": "",
                "ingredients": "1 cup rice",
                "method": "Cook rice",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/recipes/r1", response.location)
        self.assertEqual(self.fake_db["recipes"].docs[0]["title"], "New Title")

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_edit_recipe_page_shows_global_tags_in_selector(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.extend(
            [
                {
                    "_id": "r1",
                    "title": "Recipe A",
                    "meal_type": "main",
                    "source_type": "user",
                    "ingredients": [
                        {"quantity": "1", "unit": "cup", "ingredient": "rice"}
                    ],
                    "method": ["Cook rice"],
                    "notes": [],
                    "metadata": {"tags": ["quick", "batch"]},
                    "deleted_at": None,
                },
                {
                    "_id": "r2",
                    "title": "Recipe B",
                    "meal_type": "main",
                    "source_type": "user",
                    "ingredients": [
                        {"quantity": "1", "unit": "cup", "ingredient": "lentils"}
                    ],
                    "method": ["Simmer"],
                    "notes": [],
                    "metadata": {"tags": ["high-protein"]},
                    "deleted_at": None,
                },
            ]
        )

        response = self.client.get("/recipes/r1/edit")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="tags_selected"', response.data)
        self.assertIn(b'type="checkbox"', response.data)
        self.assertIn(b">quick<", response.data)
        self.assertIn(b">batch<", response.data)
        self.assertIn(b">high-protein<", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_edit_recipe_merges_selected_and_new_tags(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Old Title",
                "meal_type": "main",
                "source_type": "user",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook rice"],
                "notes": [],
                "metadata": {
                    "source": "",
                    "servings": "1",
                    "prep_time": "5",
                    "cook_time": "10",
                    "rating": "",
                    "difficulty": "",
                    "tags": ["quick"],
                },
                "deleted_at": None,
            }
        )

        response = self.client.post(
            "/recipes/r1/edit",
            data={
                "title": "New Title",
                "meal_type": "main",
                "source_type": "user",
                "source": "",
                "servings": "1",
                "prep_time": "5",
                "cook_time": "10",
                "difficulty": "",
                "rating": "",
                "tags_selected": ["quick", "batch"],
                "new_tags": "High-Protein, quick",
                "ingredients": "1 cup rice",
                "method": "Cook rice",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/recipes/r1", response.location)
        self.assertEqual(
            self.fake_db["recipes"].docs[0]["metadata"]["tags"],
            ["quick", "batch", "high-protein"],
        )

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_export_recipe_pdf(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "PDF Recipe",
                "meal_type": "main",
                "source_type": "user",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook rice"],
                "notes": [],
                "metadata": {
                    "tags": ["quick"],
                    "servings": "1",
                    "prep_time": "5",
                    "cook_time": "10",
                    "rating": "",
                    "difficulty": "",
                },
                "deleted_at": None,
            }
        )

        response = self.client.get("/recipes/r1/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.data.startswith(b"%PDF-1.4"))

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_delete_recipe_hard_deletes(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.append(
            {
                "_id": "r2",
                "title": "Delete Me",
                "meal_type": "main",
                "source_type": "user",
                "ingredients": [{"quantity": "1", "unit": "cup", "ingredient": "rice"}],
                "method": ["Cook rice"],
                "notes": [],
                "metadata": {
                    "source": "",
                    "servings": "1",
                    "prep_time": "5",
                    "cook_time": "10",
                    "rating": "",
                    "difficulty": "",
                    "tags": [],
                },
                "deleted_at": None,
            }
        )

        response = self.client.post("/recipes/r2/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/recipes", response.location)
        self.assertEqual(self.fake_db["recipes"].docs, [])


if __name__ == "__main__":
    unittest.main()
