from __future__ import annotations

import json
from typing import Any, Mapping

from flask import current_app
from pymongo.database import Database

from ..repositories import (
    GenerationRunsRepository,
    PreferencesRepository,
    RecipesRepository,
    RuntimeSettingsRepository,
    TastingProfilesRepository,
    ensure_all_indexes,
)
from .llm_adapter import LLMAdapter, LLMAdapterError
from .prompt_composer import compose_tasting_profile_prompt


def generate_tasting_profile_candidate(
    *,
    db: Database,
    model_override: str | None = None,
) -> dict[str, Any]:
    ensure_all_indexes(db)

    generation_runs_repository = GenerationRunsRepository(db)
    preferences_repository = PreferencesRepository(db)
    recipes_repository = RecipesRepository(db)
    tasting_profiles_repository = TastingProfilesRepository(db)

    model = _resolve_generation_model(db=db, model_override=model_override)
    provider = current_app.config.get("LLM_PROVIDER", "").strip()
    endpoint = current_app.config.get("LLM_ENDPOINT", "").strip()
    api_key = current_app.config.get("LLM_API_KEY", "").strip()

    if not provider or not model:
        return {
            "ok": False,
            "status_code": 503,
            "error": "Generation is not configured. Set LLM_PROVIDER and LLM_MODEL in .env.",
        }

    active_preferences = preferences_repository.get_active_profile() or {}
    dislikes = _normalize_string_list(active_preferences.get("dislikes", []))
    hard_avoids = _normalize_string_list(active_preferences.get("hard_avoids", []))

    recipes = recipes_repository.list(limit=5000)
    serialized_recipes = [_serialize_recipe_for_profile(item) for item in recipes]

    active_tasting_profile = tasting_profiles_repository.get_active_profile()
    current_profile_payload = (
        active_tasting_profile.get("profile") if active_tasting_profile else None
    )

    prompt = compose_tasting_profile_prompt(
        dislikes=dislikes,
        hard_avoids=hard_avoids,
        current_tasting_profile=current_profile_payload,
        user_recipes=serialized_recipes,
    )

    run = generation_runs_repository.create(
        {
            "meal_type": "main",
            "model": model,
            "provider": provider,
            "prompt": prompt,
            "status": "started",
        }
    )

    adapter = LLMAdapter(
        provider=provider,
        endpoint=endpoint,
        api_key=api_key,
        model=model,
    )

    try:
        raw_response = adapter.generate_recipe(prompt)
    except LLMAdapterError as exc:
        generation_runs_repository.update_status(run["_id"], "failed", error=str(exc))
        return {
            "ok": False,
            "status_code": 502,
            "error": str(exc),
            "run_id": str(run["_id"]),
        }

    errors: list[str] = []
    parsed = _parse_tasting_profile_json(raw_response=raw_response, errors=errors)
    if parsed is None:
        generation_runs_repository.update_status(
            run["_id"],
            "failed",
            raw_response=raw_response,
            error="; ".join(errors) or "Invalid tasting profile output",
        )
        return {
            "ok": False,
            "status_code": 422,
            "error": "; ".join(errors) or "Invalid tasting profile output",
            "run_id": str(run["_id"]),
        }

    normalized_profile = _normalize_generated_tasting_profile(
        parsed=parsed,
        dislikes=dislikes,
        hard_avoids=hard_avoids,
        recipe_count=len(serialized_recipes),
        errors=errors,
    )
    if normalized_profile is None:
        generation_runs_repository.update_status(
            run["_id"],
            "failed",
            raw_response=raw_response,
            error="; ".join(errors) or "Invalid tasting profile output",
        )
        return {
            "ok": False,
            "status_code": 422,
            "error": "; ".join(errors) or "Invalid tasting profile output",
            "run_id": str(run["_id"]),
        }

    candidate = tasting_profiles_repository.create_candidate(
        {
            "profile": normalized_profile,
            "input_snapshot": {
                "dislikes": dislikes,
                "hard_avoids": hard_avoids,
                "recipe_ids": [str(item.get("_id", "")).strip() for item in recipes],
                "recipe_count": len(serialized_recipes),
            },
            "llm": {
                "provider": provider,
                "model": model,
                "endpoint": endpoint,
                "prompt_template": "tasting_profile_v1",
                "prompt_text": prompt,
                "raw_response": raw_response,
                "error": "",
            },
            "generation_run_id": str(run["_id"]),
        }
    )

    generation_runs_repository.update_status(
        run["_id"],
        "succeeded",
        raw_response=raw_response,
    )

    return {
        "ok": True,
        "status_code": 201,
        "run_id": str(run["_id"]),
        "candidate_id": str(candidate["_id"]),
        "status": candidate["status"],
        "profile": candidate["profile"],
    }


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned:
            output.append(cleaned)
    return output


def _serialize_recipe_for_profile(recipe: Mapping[str, Any]) -> dict[str, Any]:
    metadata = recipe.get("metadata", {})
    if not isinstance(metadata, Mapping):
        metadata = {}

    return {
        "_id": str(recipe.get("_id", "")).strip(),
        "title": str(recipe.get("title", "")).strip(),
        "meal_type": str(recipe.get("meal_type", "")).strip(),
        "ingredients": recipe.get("ingredients", []),
        "method": recipe.get("method", []),
        "metadata": {
            "servings": metadata.get("servings", ""),
            "prep_time": metadata.get("prep_time", ""),
            "cook_time": metadata.get("cook_time", ""),
            "rating": metadata.get("rating", ""),
            "difficulty": metadata.get("difficulty", ""),
            "tags": metadata.get("tags", []),
        },
    }


def _parse_tasting_profile_json(
    *, raw_response: str, errors: list[str]
) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        errors.append("LLM output was not valid JSON")
        return None

    if isinstance(payload, dict) and isinstance(payload.get("profile"), dict):
        payload = payload["profile"]

    if not isinstance(payload, dict):
        errors.append("LLM JSON output must be an object")
        return None

    return payload


def _normalize_generated_tasting_profile(
    *,
    parsed: Mapping[str, Any],
    dislikes: list[str],
    hard_avoids: list[str],
    recipe_count: int,
    errors: list[str],
) -> dict[str, Any] | None:
    profile = dict(parsed)

    required_list_keys = [
        "core_taste_preferences_global",
        "ingredient_protein_preferences",
        "flavour_cuisine_affinities",
        "texture_dish_type_preferences",
        "cooking_behaviour_constraints",
        "inferred_avoidance_signals_red_flags",
        "ideal_constraints_for_new_suggestions",
        "known_uncertainties_data_gaps",
    ]
    for key in required_list_keys:
        if key not in profile:
            errors.append(f"Missing required profile field: {key}")
            continue
        if not isinstance(profile.get(key), list):
            errors.append(f"Profile field must be a list: {key}")

    meal_context = profile.get("meal_context_modifiers")
    if not isinstance(meal_context, Mapping):
        errors.append("Missing or invalid meal_context_modifiers")
    else:
        for key in ["main", "lunch_batch", "lunch_single", "breakfast", "dessert"]:
            if key not in meal_context:
                errors.append(f"meal_context_modifiers missing key: {key}")
            elif not isinstance(meal_context.get(key), list):
                errors.append(f"meal_context_modifiers.{key} must be a list")

    evidence = profile.get("evidence_summary")
    if not isinstance(evidence, Mapping):
        errors.append("Missing or invalid evidence_summary")

    if errors:
        return None

    profile["explicit_dislikes"] = dislikes
    profile["hard_avoids_strict"] = hard_avoids

    evidence_summary = dict(profile.get("evidence_summary") or {})
    evidence_summary["recipe_count_used"] = recipe_count
    if "high_rating_threshold" not in evidence_summary:
        evidence_summary["high_rating_threshold"] = 8
    if "low_rating_threshold" not in evidence_summary:
        evidence_summary["low_rating_threshold"] = 4
    evidence_summary["notes"] = str(evidence_summary.get("notes", "")).strip()
    profile["evidence_summary"] = evidence_summary

    return profile


def _resolve_generation_model(*, db: Database, model_override: str | None) -> str:
    override = (model_override or "").strip()
    if override:
        return override

    selected = RuntimeSettingsRepository(db).get_selected_model()
    env_model = str(current_app.config.get("LLM_MODEL", "")).strip()
    if selected:
        return selected
    return env_model
