from __future__ import annotations

import unittest

from app.repositories import (
    FeedbackEventsRepository,
    GenerationRunsRepository,
    PreferencesRepository,
    RecipesRepository,
    RuntimeSettingsRepository,
    SuggestionsRepository,
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


if __name__ == "__main__":
    unittest.main()
