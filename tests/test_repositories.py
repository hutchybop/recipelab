from __future__ import annotations

import unittest

from app.repositories import (
    FeedbackEventsRepository,
    GenerationRunsRepository,
    PreferencesRepository,
    RecipesRepository,
    RuntimeSettingsRepository,
    SuggestionsRepository,
    TastingProfilesRepository,
)

from tests.fakes import FakeDatabase


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase()

    def test_recipes_repository_create_and_list(self):
        repository = RecipesRepository(self.db)

        repository.create(
            {
                "title": "Chicken Pilaf",
                "meal_type": "main",
                "ingredients": ["300 g chicken breast"],
                "method": ["Cook"],
                "source_type": "user",
            }
        )

        recipes = repository.list()
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["title"], "Chicken Pilaf")

    def test_recipes_repository_lists_unique_normalized_tags(self):
        repository = RecipesRepository(self.db)

        repository.create(
            {
                "title": "Tagged One",
                "meal_type": "main",
                "ingredients": ["1 cup rice"],
                "method": ["Cook"],
                "source_type": "user",
                "tags": ["Quick", "High-Protein"],
            }
        )
        repository.create(
            {
                "title": "Tagged Two",
                "meal_type": "main",
                "ingredients": ["1 cup lentils"],
                "method": ["Simmer"],
                "source_type": "user",
                "tags": ["quick", "Budget"],
            }
        )

        self.assertEqual(
            repository.list_all_tags(), ["budget", "high-protein", "quick"]
        )

    def test_suggestions_repository_create_and_status_update(self):
        repository = SuggestionsRepository(self.db)
        suggestion = repository.create({"title": "New Dish", "meal_type": "main"})

        self.assertEqual(suggestion["status"], "draft")
        updated = repository.update_status(suggestion["_id"], "accepted")
        self.assertTrue(updated)

        found = repository.get_by_id(suggestion["_id"])
        assert found is not None
        self.assertEqual(found["status"], "accepted")

    def test_preferences_repository_upsert_profile(self):
        repository = PreferencesRepository(self.db)
        repository.upsert_profile({"profile_name": "default", "active": True})
        repository.upsert_profile({"profile_name": "weekend", "active": True})

        active = repository.get_active_profile()
        assert active is not None
        self.assertEqual(active["profile_name"], "weekend")

    def test_feedback_events_repository_create(self):
        repository = FeedbackEventsRepository(self.db)
        repository.create(
            {"target_type": "recipe", "target_id": "r1", "signal": "liked"}
        )

        events = repository.list_for_target(target_type="recipe", target_id="r1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal"], "liked")

    def test_feedback_events_repository_delete_reactions_and_clear_notes(self):
        repository = FeedbackEventsRepository(self.db)
        repository.create(
            {
                "target_type": "recipe",
                "target_id": "r1",
                "signal": "liked",
                "notes": "good",
            }
        )
        repository.create(
            {
                "target_type": "recipe",
                "target_id": "r1",
                "signal": "disliked",
                "notes": "bad",
            }
        )
        repository.create(
            {
                "target_type": "recipe",
                "target_id": "r1",
                "signal": "note",
                "notes": "custom",
            }
        )

        deleted = repository.delete_reactions_for_target(
            target_type="recipe", target_id="r1"
        )
        self.assertEqual(deleted, 2)
        events = repository.list_for_target(target_type="recipe", target_id="r1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal"], "note")

        repository.create(
            {
                "target_type": "recipe",
                "target_id": "r1",
                "signal": "liked",
                "notes": "keep",
            }
        )
        changed = repository.clear_notes_for_target(
            target_type="recipe", target_id="r1"
        )
        self.assertGreaterEqual(changed, 1)
        events = repository.list_for_target(target_type="recipe", target_id="r1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal"], "liked")
        self.assertEqual(events[0]["notes"], "")

    def test_generation_runs_repository_create_and_update_status(self):
        repository = GenerationRunsRepository(self.db)
        run = repository.create({"meal_type": "main", "model": "gpt-test"})
        updated = repository.update_status(run["_id"], "succeeded", raw_response="{}")

        self.assertTrue(updated)
        found = repository.get_by_id(run["_id"])
        assert found is not None
        self.assertEqual(found["status"], "succeeded")

    def test_runtime_settings_repository_persists_selected_model(self):
        repository = RuntimeSettingsRepository(self.db)
        repository.set_selected_model("gpt-5.4")

        self.assertEqual(repository.get_selected_model(), "gpt-5.4")

    def test_tasting_profiles_repository_create_candidate_and_list(self):
        repository = TastingProfilesRepository(self.db)
        candidate = repository.create_candidate(
            {
                "profile": {"core_taste_preferences_global": ["likes pulses"]},
                "input_snapshot": {
                    "dislikes": ["mushrooms"],
                    "hard_avoids": ["peanuts"],
                    "recipe_ids": ["r1", "r2"],
                    "recipe_count": 2,
                },
                "llm": {
                    "provider": "openai_compatible",
                    "model": "gpt-test",
                    "endpoint": "",
                    "prompt_template": "tasting_profile_v1",
                    "prompt_text": "prompt",
                    "raw_response": "{}",
                },
            }
        )

        self.assertEqual(candidate["status"], "candidate_pending")
        self.assertFalse(candidate["is_active"])
        self.assertEqual(candidate["review"]["decision"], "pending")

        latest = repository.get_latest_candidate()
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["_id"], candidate["_id"])

    def test_tasting_profiles_repository_accept_candidate_supersedes_previous_active(
        self,
    ):
        repository = TastingProfilesRepository(self.db)

        previous = repository.create_candidate(
            {
                "profile": {"core_taste_preferences_global": ["old"]},
                "input_snapshot": {},
                "llm": {},
            }
        )
        self.assertTrue(repository.accept_candidate(previous["_id"]))

        candidate = repository.create_candidate(
            {
                "profile": {"core_taste_preferences_global": ["new"]},
                "input_snapshot": {},
                "llm": {},
            }
        )
        accepted = repository.accept_candidate(
            candidate["_id"], decision_note="looks good"
        )
        self.assertTrue(accepted)

        active = repository.get_active_profile()
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active["_id"], candidate["_id"])
        self.assertEqual(active["status"], "accepted")
        self.assertEqual(active["review"]["decision"], "accepted")
        self.assertEqual(active["review"]["decision_note"], "looks good")

        previous_record = repository.get_by_id(previous["_id"])
        self.assertIsNotNone(previous_record)
        assert previous_record is not None
        self.assertEqual(previous_record["status"], "superseded")
        self.assertFalse(previous_record["is_active"])

    def test_tasting_profiles_repository_reject_candidate(self):
        repository = TastingProfilesRepository(self.db)
        candidate = repository.create_candidate(
            {
                "profile": {"core_taste_preferences_global": []},
                "input_snapshot": {},
                "llm": {},
            }
        )

        rejected = repository.reject_candidate(
            candidate["_id"], decision_note="not specific enough"
        )
        self.assertTrue(rejected)

        found = repository.get_by_id(candidate["_id"])
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["status"], "rejected")
        self.assertFalse(found["is_active"])
        self.assertEqual(found["review"]["decision"], "rejected")
        self.assertEqual(found["review"]["decision_note"], "not specific enough")


if __name__ == "__main__":
    unittest.main()
