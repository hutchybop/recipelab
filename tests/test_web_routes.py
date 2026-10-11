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
    def test_profile_page_shows_applied_and_rejected_history(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "likes": [],
                "dislikes": [],
                "notes": "",
                "weights": {},
            }
        )
        self.fake_db["profile_update_suggestions"].docs.extend(
            [
                {
                    "_id": "u1",
                    "action": "add_like",
                    "token": "chicken",
                    "support_count": 3,
                    "status": "applied",
                    "updated_at": 2,
                },
                {
                    "_id": "u2",
                    "action": "add_dislike",
                    "token": "cilantro",
                    "support_count": 2,
                    "status": "rejected",
                    "updated_at": 1,
                },
            ]
        )

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Applied Suggestions", response.data)
        self.assertIn(b"Rejected Suggestions", response.data)
        self.assertIn(b"chicken", response.data)
        self.assertIn(b"cilantro", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_page_can_clear_pending_suggestions_without_changing_profile(
        self, mock_db
    ):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "likes": ["beans"],
                "dislikes": ["mushrooms"],
                "notes": "Keep it savory.",
                "weights": {},
            }
        )
        self.fake_db["profile_update_suggestions"].docs.extend(
            [
                {
                    "_id": "u1",
                    "action": "add_like",
                    "token": "brown rice",
                    "status": "pending",
                },
                {
                    "_id": "u2",
                    "action": "add_dislike",
                    "token": "mushrooms",
                    "status": "applied",
                },
            ]
        )
        self.fake_db["feedback_events"].docs.append(
            {"_id": "f1", "target_type": "recipe", "target_id": "r1"}
        )

        response = self.client.post(
            "/profile", data={"action": "clear_pending_suggestions"}
        )

        self.assertEqual(response.status_code, 302)
        updates = self.fake_db["profile_update_suggestions"].docs
        self.assertEqual(updates[0]["status"], "rejected")
        self.assertEqual(updates[1]["status"], "applied")
        self.assertEqual(self.fake_db["preferences"].docs[0]["likes"], ["beans"])
        self.assertEqual(self.fake_db["preferences"].docs[0]["dislikes"], ["mushrooms"])
        self.assertEqual(len(self.fake_db["feedback_events"].docs), 1)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_suggestion_history_controls_edit_reopen_and_delete(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "likes": [],
                "dislikes": [],
                "notes": "",
                "weights": {},
            }
        )
        self.fake_db["profile_update_suggestions"].docs.extend(
            [
                {
                    "_id": "u-pending",
                    "action": "add_like",
                    "token": "brown rice",
                    "support_count": 2,
                    "status": "pending",
                    "created_at": 3,
                },
                {
                    "_id": "u-rejected",
                    "action": "add_dislike",
                    "token": "mushrooms",
                    "support_count": 2,
                    "status": "rejected",
                    "updated_at": 2,
                },
            ]
        )

        page = self.client.get("/profile")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Save Edit", page.data)
        self.assertIn(b"Accept", page.data)
        self.assertIn(b"Reopen", page.data)
        self.assertIn(b"Delete", page.data)

        edited = self.client.post(
            "/profile/suggestions/u-pending/edit",
            data={"suggestion_action": "add_dislike", "token": "red onion"},
        )
        self.assertEqual(edited.status_code, 302)
        pending = self.fake_db["profile_update_suggestions"].docs[0]
        self.assertEqual(
            (pending["action"], pending["token"]), ("add_dislike", "red onion")
        )

        reopened = self.client.post("/profile/suggestions/u-rejected/reopen")
        self.assertEqual(reopened.status_code, 302)
        self.assertEqual(
            self.fake_db["profile_update_suggestions"].docs[1]["status"], "pending"
        )

        deleted = self.client.post("/profile/suggestions/u-pending/delete")
        self.assertEqual(deleted.status_code, 302)
        self.assertEqual(
            [item["_id"] for item in self.fake_db["profile_update_suggestions"].docs],
            ["u-rejected"],
        )

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_profile_bulk_action_accepts_multiple_selected_suggestions(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "likes": [],
                "dislikes": [],
                "notes": "",
                "weights": {},
            }
        )
        self.fake_db["profile_update_suggestions"].docs.extend(
            [
                {
                    "_id": "u1",
                    "action": "add_like",
                    "token": "brown rice",
                    "status": "pending",
                    "created_at": 2,
                },
                {
                    "_id": "u2",
                    "action": "add_dislike",
                    "token": "mushrooms",
                    "status": "pending",
                    "created_at": 1,
                },
            ]
        )

        response = self.client.post(
            "/profile/suggestions/bulk",
            data={
                "suggestion_ids": ["u1", "u2"],
                "bulk_action": "accept",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [
                item["status"]
                for item in self.fake_db["profile_update_suggestions"].docs
            ],
            ["applied", "applied"],
        )
        self.assertEqual(self.fake_db["preferences"].docs[0]["likes"], ["brown rice"])
        self.assertEqual(self.fake_db["preferences"].docs[0]["dislikes"], ["mushrooms"])

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_recipe_detail_shows_feedback_state_and_history(self, mock_db):
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
        self.fake_db["feedback_events"].docs.extend(
            [
                {
                    "_id": "f2",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "note",
                    "notes": "Great texture",
                    "created_at": 2,
                },
                {
                    "_id": "f1",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "liked",
                    "notes": "",
                    "created_at": 1,
                },
            ]
        )

        response = self.client.get("/recipes/r1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Current feedback", response.data)
        self.assertIn(b"Note saved", response.data)
        self.assertIn(b"Recent feedback history", response.data)
        self.assertIn(b"Great texture", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_recipes_page_shows_reaction_and_note_badges(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["recipes"].docs.extend(
            [
                {
                    "_id": "r-liked",
                    "title": "Liked Recipe",
                    "meal_type": "main",
                    "created_at": 3,
                },
                {
                    "_id": "r-disliked",
                    "title": "Disliked Recipe",
                    "meal_type": "main",
                    "created_at": 2,
                },
                {
                    "_id": "r-note",
                    "title": "Noted Recipe",
                    "meal_type": "main",
                    "created_at": 1,
                },
            ]
        )
        self.fake_db["feedback_events"].docs.extend(
            [
                {
                    "target_type": "recipe",
                    "target_id": "r-liked",
                    "signal": "liked",
                    "notes": "Keep this note",
                    "created_at": 3,
                },
                {
                    "target_type": "recipe",
                    "target_id": "r-disliked",
                    "signal": "disliked",
                    "notes": "",
                    "created_at": 2,
                },
                {
                    "target_type": "recipe",
                    "target_id": "r-note",
                    "signal": "note",
                    "notes": "Try more lemon",
                    "created_at": 1,
                },
            ]
        )

        response = self.client.get("/recipes")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Liked Recipe", response.data)
        self.assertIn(b"Disliked", response.data)
        self.assertIn(b"Noted Recipe", response.data)
        self.assertIn(b">Note</span>", response.data)
        self.assertIn(b"Keep this note", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_suggestion_detail_shows_feedback_state_and_history(self, mock_db):
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
        self.fake_db["feedback_events"].docs.extend(
            [
                {
                    "_id": "f2",
                    "target_type": "suggestion",
                    "target_id": "s1",
                    "signal": "disliked",
                    "notes": "",
                    "created_at": 2,
                },
                {
                    "_id": "f1",
                    "target_type": "suggestion",
                    "target_id": "s1",
                    "signal": "note",
                    "notes": "Too salty",
                    "created_at": 1,
                },
            ]
        )

        response = self.client.get("/suggestions/s1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Current feedback", response.data)
        self.assertIn(b"Disliked", response.data)
        self.assertIn(b"Too salty", response.data)

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_feedback_post_creates_event(self, mock_db):
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
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.fake_db["feedback_events"].docs), 1)
        self.assertEqual(self.fake_db["feedback_events"].docs[0]["notes"], "Great")

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_feedback_post_replaces_existing_reaction(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["feedback_events"].docs.append(
            {
                "_id": "f1",
                "target_type": "recipe",
                "target_id": "r1",
                "signal": "disliked",
                "notes": "",
                "created_at": 1,
            }
        )

        response = self.client.post(
            "/feedback",
            data={
                "target_type": "recipe",
                "target_id": "r1",
                "signal": "liked",
                "notes": "",
                "return_to": "/recipes/r1",
            },
        )
        self.assertEqual(response.status_code, 302)

        events = self.fake_db["feedback_events"].docs
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal"], "liked")

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_clear_feedback_reaction_route(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["feedback_events"].docs.extend(
            [
                {
                    "_id": "f1",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "liked",
                    "notes": "",
                    "created_at": 2,
                },
                {
                    "_id": "f2",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "note",
                    "notes": "keep",
                    "created_at": 1,
                },
            ]
        )

        response = self.client.post(
            "/feedback/clear-reaction",
            data={
                "target_type": "recipe",
                "target_id": "r1",
                "return_to": "/recipes/r1",
            },
        )
        self.assertEqual(response.status_code, 302)
        events = self.fake_db["feedback_events"].docs
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal"], "note")

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_clear_feedback_note_route(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["feedback_events"].docs.extend(
            [
                {
                    "_id": "f1",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "note",
                    "notes": "remove me",
                    "created_at": 2,
                },
                {
                    "_id": "f2",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "liked",
                    "notes": "also clear",
                    "created_at": 1,
                },
            ]
        )

        response = self.client.post(
            "/feedback/clear-note",
            data={
                "target_type": "recipe",
                "target_id": "r1",
                "return_to": "/recipes/r1",
            },
        )
        self.assertEqual(response.status_code, 302)
        events = self.fake_db["feedback_events"].docs
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal"], "liked")
        self.assertEqual(events[0]["notes"], "")

    @patch("app.blueprints.web.routes.get_mongo_db")
    def test_apply_profile_suggestion_route(self, mock_db):
        mock_db.return_value = self.fake_db
        self.fake_db["preferences"].docs.append(
            {
                "_id": "p1",
                "profile_name": "default",
                "active": True,
                "hard_avoids": [],
                "likes": [],
                "dislikes": [],
                "notes": "",
                "weights": {},
            }
        )
        self.fake_db["profile_update_suggestions"].docs.append(
            {
                "_id": "u1",
                "action": "add_like",
                "token": "chicken",
                "support_count": 2,
                "status": "pending",
                "notes": "",
            }
        )

        response = self.client.post("/profile/suggestions/u1/apply")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/profile", response.location)

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
    def test_delete_recipe_soft_deletes(self, mock_db):
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
        self.assertIsNotNone(self.fake_db["recipes"].docs[0]["deleted_at"])


if __name__ == "__main__":
    unittest.main()
