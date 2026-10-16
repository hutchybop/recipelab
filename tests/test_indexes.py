from __future__ import annotations

import unittest

from app.repositories import ensure_all_indexes

from tests.fakes import FakeDatabase


class IndexTests(unittest.TestCase):
    def test_ensure_all_indexes_creates_expected_indexes(self):
        db = FakeDatabase()
        ensure_all_indexes(db)

        self.assertGreaterEqual(len(db["recipes"].indexes), 5)
        self.assertGreaterEqual(len(db["suggestions"].indexes), 3)
        self.assertGreaterEqual(len(db["preferences"].indexes), 2)
        self.assertGreaterEqual(len(db["feedback_events"].indexes), 2)
        self.assertGreaterEqual(len(db["generation_runs"].indexes), 3)
        self.assertGreaterEqual(len(db["profile_update_suggestions"].indexes), 2)
        self.assertGreaterEqual(len(db["runtime_settings"].indexes), 1)
        self.assertGreaterEqual(len(db["tasting_profiles"].indexes), 3)

        recipes_index_names = {index.get("name") for index in db["recipes"].indexes}
        self.assertIn("recipes_source_path_unique", recipes_index_names)


if __name__ == "__main__":
    unittest.main()
