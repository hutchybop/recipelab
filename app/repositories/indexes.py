from __future__ import annotations

from pymongo.database import Database

from .generation_runs_repository import GenerationRunsRepository
from .preferences_repository import PreferencesRepository
from .recipes_repository import RecipesRepository
from .runtime_settings_repository import RuntimeSettingsRepository
from .suggestions_repository import SuggestionsRepository
from .tasting_profiles_repository import TastingProfilesRepository


def ensure_all_indexes(db: Database) -> None:
    RecipesRepository.ensure_indexes(db)
    SuggestionsRepository.ensure_indexes(db)
    PreferencesRepository.ensure_indexes(db)
    GenerationRunsRepository.ensure_indexes(db)
    RuntimeSettingsRepository.ensure_indexes(db)
    TastingProfilesRepository.ensure_indexes(db)
