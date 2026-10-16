from __future__ import annotations

import json
from typing import Any, Mapping

from flask import current_app
from pymongo.database import Database

from ..repositories import (
    GenerationRunsRepository,
    RecipesRepository,
    RuntimeSettingsRepository,
    SuggestionsRepository,
    TastingProfilesRepository,
    ensure_all_indexes,
)
from .llm_adapter import LLMAdapter, LLMAdapterError
from .prompt_composer import compose_canonical_conversion_prompt, compose_recipe_prompt
from .schema_utils import normalize_recipe_document


def generate_recipe_suggestion(
    *,
    db: Database,
    meal_type: str,
    instructions: str,
    model_override: str | None = None,
    selected_recipe_ids: list[str] | None = None,
) -> dict[str, Any]:
    ensure_all_indexes(db)

    generation_runs_repository = GenerationRunsRepository(db)
    suggestions_repository = SuggestionsRepository(db)
    tasting_profiles_repository = TastingProfilesRepository(db)
    recipes_repository = RecipesRepository(db)

    active_tasting_profile = tasting_profiles_repository.get_active_profile()
    if not active_tasting_profile:
        return {
            "ok": False,
            "status_code": 409,
            "error": "No accepted tasting profile found. Go to Profile to generate and accept one first.",
        }

    requested_ids = _normalize_selected_recipe_ids(selected_recipe_ids)
    if len(requested_ids) > 4:
        return {
            "ok": False,
            "status_code": 400,
            "error": "You can select up to 4 reference recipes.",
        }

    reference_recipes = _load_reference_recipes(
        recipes_repository=recipes_repository,
        recipe_ids=requested_ids,
    )

    model = _resolve_generation_model(db=db, model_override=model_override)
    provider = current_app.config.get("LLM_PROVIDER", "").strip()
    endpoint = current_app.config.get("LLM_ENDPOINT", "").strip()
    api_key = current_app.config.get("LLM_API_KEY", "").strip()

    if not provider or not model:
        missing = []
        if not provider:
            missing.append("LLM_PROVIDER")
        if not model:
            missing.append("LLM_MODEL or runtime model selection")
        return {
            "ok": False,
            "status_code": 503,
            "error": (
                "Generation is not configured: missing "
                + ", ".join(missing)
                + ". Set provider/model env vars and ensure a valid model is selected in Settings."
            ),
        }

    prompt = compose_recipe_prompt(
        meal_type=meal_type,
        instructions=instructions,
        profile={},
        tasting_profile=active_tasting_profile.get("profile", {}),
        selected_recipes=reference_recipes,
    )

    run = generation_runs_repository.create(
        {
            "meal_type": meal_type,
            "model": model,
            "provider": provider,
            "prompt": prompt,
            "status": "started",
        }
    )

    adapter = LLMAdapter(
        provider=provider, endpoint=endpoint, api_key=api_key, model=model
    )

    try:
        raw_response = adapter.generate_recipe(prompt)
    except LLMAdapterError as exc:
        detailed_error = (
            f"Recipe generation failed for provider '{provider}' model '{model}': {exc}"
        )
        generation_runs_repository.update_status(run["_id"], "failed", error=str(exc))
        return {
            "ok": False,
            "status_code": 502,
            "error": detailed_error,
            "run_id": str(run["_id"]),
        }

    suggestion = _persist_suggestion_from_raw_response(
        suggestions_repository=suggestions_repository,
        raw_response=raw_response,
        meal_type=meal_type,
        generation_run_id=str(run["_id"]),
        source_type="ai",
        default_source="AI Generated",
    )

    status = suggestion["status"]
    validation_errors = suggestion["validation"]["errors"]

    if status == "draft":
        generation_runs_repository.update_status(
            run["_id"], "succeeded", raw_response=raw_response
        )
    else:
        generation_runs_repository.update_status(
            run["_id"],
            "failed",
            raw_response=raw_response,
            error="; ".join(validation_errors) or "Invalid recipe output",
        )

    return {
        "ok": True,
        "status_code": 201 if status == "draft" else 422,
        "run_id": str(run["_id"]),
        "suggestion_id": str(suggestion["_id"]),
        "status": status,
        "validation": suggestion["validation"],
        "recipe": suggestion["recipe"],
    }


def convert_raw_recipe_to_suggestion(
    *,
    db: Database,
    meal_type: str,
    raw_recipe_text: str,
    model_override: str | None = None,
) -> dict[str, Any]:
    ensure_all_indexes(db)

    generation_runs_repository = GenerationRunsRepository(db)
    suggestions_repository = SuggestionsRepository(db)
    recipes_repository = RecipesRepository(db)
    existing_tags = recipes_repository.list_all_tags()

    model = _resolve_generation_model(db=db, model_override=model_override)
    provider = current_app.config.get("LLM_PROVIDER", "").strip()
    endpoint = current_app.config.get("LLM_ENDPOINT", "").strip()
    api_key = current_app.config.get("LLM_API_KEY", "").strip()

    if not provider or not model:
        missing = []
        if not provider:
            missing.append("LLM_PROVIDER")
        if not model:
            missing.append("LLM_MODEL or runtime model selection")
        return {
            "ok": False,
            "status_code": 503,
            "error": (
                "Generation is not configured: missing "
                + ", ".join(missing)
                + ". Set provider/model env vars and ensure a valid model is selected in Settings."
            ),
        }

    prompt = compose_canonical_conversion_prompt(
        meal_type=meal_type,
        raw_recipe_text=raw_recipe_text,
        allowed_tags=existing_tags,
    )

    run = generation_runs_repository.create(
        {
            "meal_type": meal_type,
            "model": model,
            "provider": provider,
            "prompt": prompt,
            "status": "started",
        }
    )

    adapter = LLMAdapter(
        provider=provider, endpoint=endpoint, api_key=api_key, model=model
    )

    try:
        raw_response = adapter.generate_recipe(prompt)
    except LLMAdapterError as exc:
        detailed_error = (
            f"Recipe conversion failed for provider '{provider}' model '{model}': {exc}"
        )
        generation_runs_repository.update_status(run["_id"], "failed", error=str(exc))
        return {
            "ok": False,
            "status_code": 502,
            "error": detailed_error,
            "run_id": str(run["_id"]),
        }

    suggestion = _persist_suggestion_from_raw_response(
        suggestions_repository=suggestions_repository,
        raw_response=raw_response,
        meal_type=meal_type,
        generation_run_id=str(run["_id"]),
        source_type="user",
        default_source="Imported raw recipe",
        allowed_tags=existing_tags,
    )

    if suggestion["status"] == "draft":
        generation_runs_repository.update_status(
            run["_id"], "succeeded", raw_response=raw_response
        )
    else:
        generation_runs_repository.update_status(
            run["_id"],
            "failed",
            raw_response=raw_response,
            error="; ".join(suggestion["validation"]["errors"])
            or "Invalid recipe output",
        )

    return {
        "ok": True,
        "status_code": 201 if suggestion["status"] == "draft" else 422,
        "run_id": str(run["_id"]),
        "suggestion_id": str(suggestion["_id"]),
        "status": suggestion["status"],
        "validation": suggestion["validation"],
        "recipe": suggestion["recipe"],
    }


def _persist_suggestion_from_raw_response(
    *,
    suggestions_repository: SuggestionsRepository,
    raw_response: str,
    meal_type: str,
    generation_run_id: str,
    source_type: str,
    default_source: str,
    allowed_tags: list[str] | None = None,
) -> dict[str, Any]:
    validation_errors: list[str] = []
    parsed_recipe = _parse_recipe_json(raw_response, validation_errors)

    suggestion_recipe: dict[str, Any]
    status: str
    if parsed_recipe is None:
        suggestion_recipe = {
            "meal_type": meal_type,
            "source_type": source_type,
            "raw_response": raw_response,
        }
        status = "draft_invalid"
    else:
        try:
            suggestion_recipe = normalize_recipe_document(
                {
                    "title": parsed_recipe.get("title", "Untitled suggestion"),
                    "meal_type": meal_type,
                    "source_type": source_type,
                    "source": parsed_recipe.get("source", default_source),
                    "servings": parsed_recipe.get("servings", ""),
                    "prep_time": parsed_recipe.get("prep_time", ""),
                    "cook_time": parsed_recipe.get("cook_time", ""),
                    "rating": parsed_recipe.get("rating", ""),
                    "difficulty": parsed_recipe.get("difficulty", ""),
                    "tags": _filter_to_allowed_tags(
                        parsed_recipe.get("tags", []), allowed_tags
                    ),
                    "ingredients": parsed_recipe.get("ingredients", []),
                    "method": parsed_recipe.get("method", []),
                    "notes": parsed_recipe.get("notes", []),
                }
            )
            status = "draft"
        except ValueError as exc:
            validation_errors.append(str(exc))
            suggestion_recipe = {
                "meal_type": meal_type,
                "source_type": source_type,
                "raw_response": raw_response,
            }
            status = "draft_invalid"

    return suggestions_repository.create(
        {
            "title": (
                parsed_recipe.get("title")
                if parsed_recipe
                else "Invalid suggestion output"
            ),
            "meal_type": meal_type,
            "status": status,
            "generation_run_id": generation_run_id,
            "validation": {
                "valid": status == "draft",
                "errors": validation_errors,
            },
            "recipe": suggestion_recipe,
        }
    )


def _parse_recipe_json(
    raw_response: str, errors: list[str]
) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        errors.append("LLM output was not valid JSON")
        return None

    if isinstance(payload, dict) and isinstance(payload.get("recipe"), dict):
        payload = payload["recipe"]

    if not isinstance(payload, dict):
        errors.append("LLM JSON output must be an object")
        return None

    return payload


def _filter_to_allowed_tags(raw_tags: Any, allowed_tags: list[str] | None) -> Any:
    if allowed_tags is None:
        return raw_tags

    if not isinstance(raw_tags, list):
        return []

    allowed = {item.strip().lower() for item in allowed_tags if isinstance(item, str)}
    if not allowed:
        return []

    filtered: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        if not isinstance(tag, str):
            continue
        cleaned = tag.strip().lower()
        if not cleaned or cleaned not in allowed or cleaned in seen:
            continue
        seen.add(cleaned)
        filtered.append(cleaned)

    return filtered


def get_allowed_models() -> list[str]:
    raw = str(current_app.config.get("LLM_ALLOWED_MODELS", "")).strip()
    from_env = [item.strip() for item in raw.split(",") if item.strip()]
    fallback = str(current_app.config.get("LLM_MODEL", "")).strip()

    models = from_env or ([fallback] if fallback else [])
    unique_models: list[str] = []
    for model in models:
        if model not in unique_models:
            unique_models.append(model)
    return unique_models


def get_effective_model(db: Database) -> str:
    allowed_models = get_allowed_models()
    env_model = str(current_app.config.get("LLM_MODEL", "")).strip()
    selected = RuntimeSettingsRepository(db).get_selected_model()

    if selected and selected in allowed_models:
        return selected
    if env_model and env_model in allowed_models:
        return env_model
    if allowed_models:
        return allowed_models[0]
    return selected or env_model


def _resolve_generation_model(*, db: Database, model_override: str | None) -> str:
    override = (model_override or "").strip()
    if override:
        return override
    return get_effective_model(db)


def _normalize_selected_recipe_ids(selected_recipe_ids: list[str] | None) -> list[str]:
    unique_ids: list[str] = []
    for raw in selected_recipe_ids or []:
        if not isinstance(raw, str):
            continue
        cleaned = raw.strip()
        if cleaned and cleaned not in unique_ids:
            unique_ids.append(cleaned)
    return unique_ids


def _load_reference_recipes(
    *, recipes_repository: RecipesRepository, recipe_ids: list[str]
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for recipe_id in recipe_ids[:4]:
        recipe = recipes_repository.get_by_id(recipe_id)
        if not recipe or recipe.get("deleted_at") is not None:
            continue
        metadata = recipe.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        selected.append(
            {
                "id": str(recipe.get("_id", "")).strip(),
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
        )
    return selected
