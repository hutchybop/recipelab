from __future__ import annotations

import unittest

from app.services.profile_refinement_service import (
    apply_profile_update_suggestion,
    bulk_manage_profile_update_suggestions,
    delete_profile_update_suggestion,
    edit_profile_update_suggestion,
    generate_profile_update_suggestions,
    reopen_profile_update_suggestion,
    reject_profile_update_suggestion,
    undo_profile_update_suggestion,
    _extract_tokens,
)
from app.services.prompt_composer import compose_recipe_prompt

from tests.fakes import FakeDatabase


class ProfileRefinementServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase()
        self.db["preferences"].docs.append(
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

    def test_generate_profile_update_suggestions_creates_pending_items(self):
        self.db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Chicken Bowl",
                "metadata": {"tags": ["spicy"]},
                "ingredients": [
                    {"quantity": "1", "unit": "lb", "ingredient": "chicken breast"},
                    {"quantity": "1", "unit": "cup", "ingredient": "rice"},
                ],
            }
        )
        self.db["recipes"].docs.append(
            {
                "_id": "r2",
                "title": "Chicken and Rice",
                "metadata": {"tags": ["spicy"]},
                "ingredients": [
                    {"quantity": "1", "unit": "lb", "ingredient": "chicken breast"},
                    {"quantity": "1", "unit": "cup", "ingredient": "rice"},
                ],
            }
        )
        self.db["feedback_events"].docs.extend(
            [
                {
                    "_id": "f1",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "liked",
                    "created_at": 2,
                },
                {
                    "_id": "f2",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "liked",
                    "created_at": 1,
                },
                {
                    "_id": "f3",
                    "target_type": "recipe",
                    "target_id": "r2",
                    "signal": "liked",
                    "created_at": 0,
                },
            ]
        )

        result = generate_profile_update_suggestions(self.db, min_support=2)
        self.assertGreaterEqual(result["created"], 1)
        self.assertGreaterEqual(len(self.db["profile_update_suggestions"].docs), 1)

    def test_apply_and_reject_profile_update_suggestions(self):
        self.db["profile_update_suggestions"].docs.append(
            {
                "_id": "u1",
                "action": "add_like",
                "token": "chicken",
                "support_count": 3,
                "status": "pending",
                "notes": "",
            }
        )

        ok, _ = apply_profile_update_suggestion(self.db, "u1")
        self.assertTrue(ok)
        self.assertIn(
            "chicken",
            [item.lower() for item in self.db["preferences"].docs[0]["likes"]],
        )
        self.assertEqual(
            self.db["profile_update_suggestions"].docs[0]["status"], "applied"
        )

        self.db["profile_update_suggestions"].docs.append(
            {
                "_id": "u2",
                "action": "add_dislike",
                "token": "mushroom",
                "support_count": 2,
                "status": "pending",
                "notes": "",
            }
        )
        rejected = reject_profile_update_suggestion(self.db, "u2")
        self.assertTrue(rejected)
        self.assertEqual(
            self.db["profile_update_suggestions"].docs[1]["status"], "rejected"
        )

    def test_generate_profile_update_suggestions_uses_latest_reaction_per_target(self):
        self.db["recipes"].docs.append(
            {
                "_id": "r1",
                "title": "Chicken Bowl",
                "metadata": {"tags": ["spicy"]},
                "ingredients": [
                    {"quantity": "1", "unit": "lb", "ingredient": "chicken breast"},
                ],
            }
        )
        self.db["feedback_events"].docs.extend(
            [
                {
                    "_id": "f2",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "liked",
                    "created_at": 2,
                },
                {
                    "_id": "f1",
                    "target_type": "recipe",
                    "target_id": "r1",
                    "signal": "disliked",
                    "created_at": 1,
                },
            ]
        )

        result = generate_profile_update_suggestions(self.db, min_support=1)
        self.assertGreaterEqual(result["created"], 1)
        actions = {
            (item["action"], item["token"])
            for item in self.db["profile_update_suggestions"].docs
        }
        self.assertIn(("add_like", "chicken breast"), actions)
        self.assertNotIn(("add_dislike", "chicken breast"), actions)

    def test_extract_tokens_preserves_ingredient_phrases_and_removes_prep_noise(self):
        tokens = _extract_tokens(
            {
                "metadata": {"tags": ["brown-rice"]},
                "ingredients": [
                    {"ingredient": "brown rice"},
                    {"ingredient": "dark chocolate, melted"},
                    {"ingredient": "thin steaks, chopped"},
                    {"ingredient": "red onion, skin removed"},
                ],
            }
        )

        self.assertEqual(
            tokens,
            {"brown rice", "dark chocolate", "steaks", "red onion"},
        )

    def test_refresh_rejects_obsolete_single_word_suggestions(self):
        for recipe_id in ("r1", "r2"):
            self.db["recipes"].docs.append(
                {
                    "_id": recipe_id,
                    "title": "Brown Rice Bowl",
                    "metadata": {"tags": []},
                    "ingredients": [{"ingredient": "brown rice"}],
                }
            )
            self.db["feedback_events"].docs.append(
                {
                    "_id": f"f-{recipe_id}",
                    "target_type": "recipe",
                    "target_id": recipe_id,
                    "signal": "liked",
                    "created_at": 1,
                }
            )

        self.db["profile_update_suggestions"].docs.extend(
            [
                {
                    "_id": "old-brown",
                    "action": "add_like",
                    "token": "brown",
                    "support_count": 2,
                    "status": "pending",
                    "created_at": 1,
                },
                {
                    "_id": "old-rice",
                    "action": "add_like",
                    "token": "rice",
                    "support_count": 2,
                    "status": "pending",
                    "created_at": 2,
                },
            ]
        )

        generate_profile_update_suggestions(self.db, min_support=2)

        suggestions = self.db["profile_update_suggestions"].docs
        pending = {
            item["token"] for item in suggestions if item.get("status") == "pending"
        }
        self.assertEqual(pending, {"brown rice"})
        self.assertTrue(
            all(
                item.get("status") == "rejected"
                for item in suggestions
                if item["token"] in {"brown", "rice"}
            )
        )

    def test_edit_applied_suggestion_updates_the_profile_used_in_prompts(self):
        self.db["preferences"].docs[0]["likes"] = ["beans"]
        self.db["profile_update_suggestions"].docs.append(
            {
                "_id": "u-applied",
                "action": "add_like",
                "token": "beans",
                "status": "applied",
            }
        )

        ok, _ = edit_profile_update_suggestion(
            self.db, "u-applied", action="add_dislike", token="red onion"
        )

        self.assertTrue(ok)
        profile = self.db["preferences"].docs[0]
        self.assertEqual(profile["likes"], [])
        self.assertEqual(profile["dislikes"], ["red onion"])
        prompt = compose_recipe_prompt(
            meal_type="main", instructions="", profile=profile
        )
        self.assertIn("- dislikes: red onion", prompt)
        self.assertIn("- likes: (none provided)", prompt)
        record = self.db["profile_update_suggestions"].docs[0]
        self.assertEqual(
            (record["action"], record["token"], record["status"]),
            ("add_dislike", "red onion", "applied"),
        )

    def test_undo_applied_suggestion_removes_its_prompt_preference(self):
        self.db["preferences"].docs[0]["likes"] = ["chicken"]
        self.db["profile_update_suggestions"].docs.append(
            {
                "_id": "u-applied",
                "action": "add_like",
                "token": "chicken",
                "status": "applied",
            }
        )

        ok, _ = undo_profile_update_suggestion(self.db, "u-applied")

        self.assertTrue(ok)
        self.assertEqual(self.db["preferences"].docs[0]["likes"], [])
        self.assertEqual(
            self.db["profile_update_suggestions"].docs[0]["status"], "reverted"
        )

    def test_edit_and_reopen_rejected_suggestion_does_not_apply_it(self):
        self.db["profile_update_suggestions"].docs.append(
            {
                "_id": "u-rejected",
                "action": "add_like",
                "token": "beans",
                "status": "rejected",
            }
        )

        ok, _ = edit_profile_update_suggestion(
            self.db, "u-rejected", action="add_dislike", token="mushrooms"
        )
        reopened = reopen_profile_update_suggestion(self.db, "u-rejected")

        self.assertTrue(ok)
        self.assertTrue(reopened)
        self.assertEqual(self.db["preferences"].docs[0]["dislikes"], [])
        record = self.db["profile_update_suggestions"].docs[0]
        self.assertEqual(
            (record["action"], record["token"], record["status"]),
            ("add_dislike", "mushrooms", "pending"),
        )

    def test_delete_applied_suggestion_removes_record_and_prompt_preference(self):
        self.db["preferences"].docs[0]["dislikes"] = ["mushrooms"]
        self.db["profile_update_suggestions"].docs.append(
            {
                "_id": "u-applied",
                "action": "add_dislike",
                "token": "mushrooms",
                "status": "applied",
            }
        )

        ok, _ = delete_profile_update_suggestion(self.db, "u-applied")

        self.assertTrue(ok)
        self.assertEqual(self.db["profile_update_suggestions"].docs, [])
        self.assertEqual(self.db["preferences"].docs[0]["dislikes"], [])

    def test_rejected_suggestion_is_suppressed_until_reopened(self):
        for recipe_id in ("r1", "r2"):
            self.db["recipes"].docs.append(
                {
                    "_id": recipe_id,
                    "title": "Brown Rice Bowl",
                    "metadata": {"tags": []},
                    "ingredients": [{"ingredient": "brown rice"}],
                }
            )
            self.db["feedback_events"].docs.append(
                {
                    "_id": f"f-{recipe_id}",
                    "target_type": "recipe",
                    "target_id": recipe_id,
                    "signal": "liked",
                    "created_at": 1,
                }
            )
        self.db["profile_update_suggestions"].docs.append(
            {
                "_id": "u-rejected",
                "action": "add_like",
                "token": "brown rice",
                "status": "rejected",
                "updated_at": 1,
            }
        )

        result = generate_profile_update_suggestions(self.db, min_support=2)
        self.assertEqual(result["created"], 0)
        self.assertTrue(reopen_profile_update_suggestion(self.db, "u-rejected"))
        generate_profile_update_suggestions(self.db, min_support=2)
        self.assertEqual(
            self.db["profile_update_suggestions"].docs[0]["status"], "pending"
        )

    def test_bulk_accept_reject_and_delete_respect_each_suggestion_state(self):
        self.db["preferences"].docs[0]["likes"] = ["chicken"]
        self.db["profile_update_suggestions"].docs.extend(
            [
                {
                    "_id": "u-pending",
                    "action": "add_like",
                    "token": "beans",
                    "status": "pending",
                },
                {
                    "_id": "u-applied",
                    "action": "add_like",
                    "token": "chicken",
                    "status": "applied",
                },
                {
                    "_id": "u-rejected",
                    "action": "add_dislike",
                    "token": "mushrooms",
                    "status": "rejected",
                },
                {
                    "_id": "u-delete",
                    "action": "add_like",
                    "token": "rice",
                    "status": "rejected",
                },
            ]
        )

        accepted = bulk_manage_profile_update_suggestions(
            self.db, ["u-pending"], operation="accept"
        )
        rejected = bulk_manage_profile_update_suggestions(
            self.db, ["u-applied"], operation="reject"
        )
        restored = bulk_manage_profile_update_suggestions(
            self.db, ["u-rejected"], operation="accept"
        )
        deleted = bulk_manage_profile_update_suggestions(
            self.db, ["u-delete"], operation="delete"
        )

        self.assertEqual(accepted["updated"], 1)
        self.assertEqual(rejected["updated"], 1)
        self.assertEqual(restored["updated"], 1)
        self.assertEqual(deleted["deleted"], 1)
        statuses = {
            item["_id"]: item["status"]
            for item in self.db["profile_update_suggestions"].docs
        }
        self.assertEqual(statuses["u-pending"], "applied")
        self.assertEqual(statuses["u-applied"], "rejected")
        self.assertEqual(statuses["u-rejected"], "applied")
        self.assertNotIn("u-delete", statuses)
        profile = self.db["preferences"].docs[0]
        self.assertEqual(set(profile["likes"]), {"beans"})
        self.assertEqual(profile["dislikes"], ["mushrooms"])


if __name__ == "__main__":
    unittest.main()
