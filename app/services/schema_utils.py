from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping


MEAL_TYPES = {"main", "lunch_batch", "lunch_single", "breakfast", "dessert"}
SUGGESTION_STATUSES = {"draft", "accepted", "rejected", "draft_invalid"}
GENERATION_RUN_STATUSES = {"started", "succeeded", "failed"}
TASTING_PROFILE_STATUSES = {"candidate_pending", "accepted", "rejected", "superseded"}
TASTING_PROFILE_DECISIONS = {"pending", "accepted", "rejected"}

_UNIT_PATTERN = re.compile(
    r"^(g|kg|ml|l|tsp|tbsp|cup|cups|oz|lb|clove|cloves|pinch|handful|handfuls)$",
    re.IGNORECASE,
)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _clean_string(value: Any, *, field_name: str, required: bool = False) -> str:
    if value is None:
        value = ""
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{field_name} is required")
    return cleaned


def _string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, Iterable):
        output: list[str] = []
        for item in value:
            if item is None:
                continue
            if not isinstance(item, str):
                raise ValueError(f"{field_name} items must be strings")
            cleaned = item.strip()
            if cleaned:
                output.append(cleaned)
        return output
    raise ValueError(f"{field_name} must be a list of strings")


def _parse_ingredient_line(line: str) -> dict[str, str]:
    cleaned = line.strip().lstrip("-").strip()
    if not cleaned:
        return {"quantity": "", "unit": "", "ingredient": ""}

    tokens = cleaned.split()
    quantity = ""
    unit = ""
    remaining = tokens

    if tokens and re.match(r"^[0-9]+(?:[./-][0-9]+)?$", tokens[0]):
        quantity = tokens[0]
        remaining = tokens[1:]

    if remaining and _UNIT_PATTERN.match(remaining[0]):
        unit = remaining[0]
        remaining = remaining[1:]

    ingredient = " ".join(remaining).strip() if remaining else cleaned
    return {"quantity": quantity, "unit": unit, "ingredient": ingredient}


def _normalize_ingredients(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []

    normalized: list[dict[str, str]] = []
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ValueError("ingredients must be a list")

    for item in value:
        if isinstance(item, str):
            parsed = _parse_ingredient_line(item)
        elif isinstance(item, Mapping):
            parsed = {
                "quantity": _clean_string(
                    item.get("quantity", ""), field_name="ingredients.quantity"
                ),
                "unit": _clean_string(
                    item.get("unit", ""), field_name="ingredients.unit"
                ),
                "ingredient": _clean_string(
                    item.get("ingredient", ""),
                    field_name="ingredients.ingredient",
                    required=True,
                ),
            }
        else:
            raise ValueError("ingredient items must be strings or objects")

        if parsed["ingredient"]:
            normalized.append(parsed)

    return normalized


def _normalize_method_steps(value: Any) -> list[str]:
    steps = _string_list(value, field_name="method")
    return [step for step in steps if step]


def _normalize_meal_type(value: Any) -> str:
    meal_type = _clean_string(value, field_name="meal_type", required=True)
    if meal_type not in MEAL_TYPES:
        raise ValueError(f"meal_type must be one of {sorted(MEAL_TYPES)}")
    return meal_type


def normalize_recipe_document(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(document))

    metadata = dict(payload.get("metadata") or {})
    tags = payload.get("tags", metadata.get("tags", []))

    normalized = {
        "title": _clean_string(payload.get("title"), field_name="title", required=True),
        "meal_type": _normalize_meal_type(payload.get("meal_type")),
        "source_type": _clean_string(
            payload.get("source_type", "user"), field_name="source_type", required=True
        ),
        "source_path": _clean_string(
            payload.get("source_path", ""), field_name="source_path"
        ),
        "ingredients": _normalize_ingredients(payload.get("ingredients", [])),
        "method": _normalize_method_steps(payload.get("method", [])),
        "notes": _string_list(payload.get("notes", []), field_name="notes"),
        "metadata": {
            "source": _clean_string(
                payload.get("source", metadata.get("source", "")),
                field_name="metadata.source",
            ),
            "servings": _clean_string(
                payload.get("servings", metadata.get("servings", "")),
                field_name="metadata.servings",
            ),
            "prep_time": _clean_string(
                payload.get("prep_time", metadata.get("prep_time", "")),
                field_name="metadata.prep_time",
            ),
            "cook_time": _clean_string(
                payload.get("cook_time", metadata.get("cook_time", "")),
                field_name="metadata.cook_time",
            ),
            "rating": _clean_string(
                payload.get("rating", metadata.get("rating", "")),
                field_name="metadata.rating",
            ),
            "difficulty": _clean_string(
                payload.get("difficulty", metadata.get("difficulty", "")),
                field_name="metadata.difficulty",
            ),
            "tags": _string_list(tags, field_name="metadata.tags"),
        },
        "created_at": payload.get("created_at") or utc_now(),
        "updated_at": utc_now(),
        "deleted_at": payload.get("deleted_at"),
    }

    if not normalized["method"]:
        raise ValueError("method must contain at least one step")

    return normalized


def normalize_recipe_update(update_fields: Mapping[str, Any]) -> dict[str, Any]:
    if not update_fields:
        raise ValueError("update_fields cannot be empty")

    allowed_fields = {
        "title",
        "meal_type",
        "source_type",
        "source_path",
        "ingredients",
        "method",
        "notes",
        "metadata",
        "source",
        "servings",
        "prep_time",
        "cook_time",
        "rating",
        "difficulty",
        "tags",
    }
    unknown = set(update_fields) - allowed_fields
    if unknown:
        raise ValueError(f"unsupported recipe update fields: {sorted(unknown)}")

    base = {
        "title": update_fields.get("title", "Untitled"),
        "meal_type": update_fields.get("meal_type", "main"),
        "source_type": update_fields.get("source_type", "user"),
        "source_path": update_fields.get("source_path", ""),
        "ingredients": update_fields.get("ingredients", ["1 item placeholder"]),
        "method": update_fields.get("method", ["placeholder step"]),
        "notes": update_fields.get("notes", []),
        "metadata": update_fields.get("metadata", {}),
        "source": update_fields.get("source", ""),
        "servings": update_fields.get("servings", ""),
        "prep_time": update_fields.get("prep_time", ""),
        "cook_time": update_fields.get("cook_time", ""),
        "rating": update_fields.get("rating", ""),
        "difficulty": update_fields.get("difficulty", ""),
        "tags": update_fields.get("tags", []),
    }

    normalized = normalize_recipe_document(base)
    normalized_update: dict[str, Any] = {"updated_at": utc_now()}

    for key in update_fields:
        if key in {
            "source",
            "servings",
            "prep_time",
            "cook_time",
            "rating",
            "difficulty",
            "tags",
        }:
            normalized_update.setdefault("metadata", {})
            normalized_update["metadata"][key] = normalized["metadata"][key]
        else:
            normalized_update[key] = normalized[key]

    return normalized_update


def normalize_suggestion_document(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(document))
    status = _clean_string(
        payload.get("status", "draft"), field_name="status", required=True
    )
    if status not in SUGGESTION_STATUSES:
        raise ValueError(f"status must be one of {sorted(SUGGESTION_STATUSES)}")

    normalized = {
        "title": _clean_string(
            payload.get("title", "Untitled suggestion"),
            field_name="title",
            required=True,
        ),
        "meal_type": _normalize_meal_type(payload.get("meal_type", "main")),
        "status": status,
        "generation_run_id": _clean_string(
            payload.get("generation_run_id", ""), field_name="generation_run_id"
        ),
        "validation": payload.get("validation", {}),
        "recipe": payload.get("recipe", {}),
        "created_at": payload.get("created_at") or utc_now(),
        "updated_at": utc_now(),
    }
    return normalized


def normalize_preference_document(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(document))
    normalized = {
        "profile_name": _clean_string(
            payload.get("profile_name", "default"),
            field_name="profile_name",
            required=True,
        ),
        "active": bool(payload.get("active", True)),
        "hard_avoids": _string_list(
            payload.get("hard_avoids", []), field_name="hard_avoids"
        ),
        "likes": _string_list(payload.get("likes", []), field_name="likes"),
        "dislikes": _string_list(payload.get("dislikes", []), field_name="dislikes"),
        "notes": _clean_string(payload.get("notes", ""), field_name="notes"),
        "weights": dict(payload.get("weights", {})),
        "created_at": payload.get("created_at") or utc_now(),
        "updated_at": utc_now(),
    }
    return normalized


def normalize_generation_run_status(status: Any) -> str:
    normalized = _clean_string(status, field_name="status", required=True)
    if normalized not in GENERATION_RUN_STATUSES:
        raise ValueError(f"status must be one of {sorted(GENERATION_RUN_STATUSES)}")
    return normalized


def normalize_generation_run_document(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(document))
    normalized = {
        "meal_type": _normalize_meal_type(payload.get("meal_type", "main")),
        "model": _clean_string(
            payload.get("model", "unknown"), field_name="model", required=True
        ),
        "provider": _clean_string(payload.get("provider", ""), field_name="provider"),
        "prompt": _clean_string(payload.get("prompt", ""), field_name="prompt"),
        "status": normalize_generation_run_status(payload.get("status", "started")),
        "raw_response": _clean_string(
            payload.get("raw_response", ""), field_name="raw_response"
        ),
        "error": _clean_string(payload.get("error", ""), field_name="error"),
        "created_at": payload.get("created_at") or utc_now(),
        "updated_at": utc_now(),
    }
    return normalized


def normalize_tasting_profile_status(status: Any) -> str:
    normalized = _clean_string(status, field_name="status", required=True)
    if normalized not in TASTING_PROFILE_STATUSES:
        raise ValueError(f"status must be one of {sorted(TASTING_PROFILE_STATUSES)}")
    return normalized


def normalize_tasting_profile_document(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(document))
    status = normalize_tasting_profile_status(
        payload.get("status", "candidate_pending")
    )
    is_active = bool(payload.get("is_active", False))

    review_payload = payload.get("review") or {}
    decision = _clean_string(
        review_payload.get("decision", "pending"),
        field_name="review.decision",
        required=True,
    )
    if decision not in TASTING_PROFILE_DECISIONS:
        raise ValueError(
            f"review.decision must be one of {sorted(TASTING_PROFILE_DECISIONS)}"
        )

    profile = payload.get("profile", {})
    if not isinstance(profile, Mapping):
        raise ValueError("profile must be an object")

    input_snapshot = payload.get("input_snapshot", {})
    if not isinstance(input_snapshot, Mapping):
        raise ValueError("input_snapshot must be an object")

    llm = payload.get("llm", {})
    if not isinstance(llm, Mapping):
        raise ValueError("llm must be an object")

    normalized = {
        "status": status,
        "is_active": is_active,
        "profile": dict(profile),
        "input_snapshot": {
            "dislikes": _string_list(
                input_snapshot.get("dislikes", []), field_name="input_snapshot.dislikes"
            ),
            "hard_avoids": _string_list(
                input_snapshot.get("hard_avoids", []),
                field_name="input_snapshot.hard_avoids",
            ),
            "recipe_ids": _string_list(
                input_snapshot.get("recipe_ids", []),
                field_name="input_snapshot.recipe_ids",
            ),
            "recipe_count": int(input_snapshot.get("recipe_count", 0) or 0),
            "active_tasting_profile_id": _clean_string(
                input_snapshot.get("active_tasting_profile_id", ""),
                field_name="input_snapshot.active_tasting_profile_id",
            ),
        },
        "llm": {
            "provider": _clean_string(
                llm.get("provider", ""), field_name="llm.provider"
            ),
            "model": _clean_string(llm.get("model", ""), field_name="llm.model"),
            "endpoint": _clean_string(
                llm.get("endpoint", ""), field_name="llm.endpoint"
            ),
            "prompt_template": _clean_string(
                llm.get("prompt_template", ""), field_name="llm.prompt_template"
            ),
            "prompt_text": _clean_string(
                llm.get("prompt_text", ""), field_name="llm.prompt_text"
            ),
            "raw_response": _clean_string(
                llm.get("raw_response", ""), field_name="llm.raw_response"
            ),
            "error": _clean_string(llm.get("error", ""), field_name="llm.error"),
        },
        "review": {
            "decision": decision,
            "decision_note": _clean_string(
                review_payload.get("decision_note", ""),
                field_name="review.decision_note",
            ),
            "decided_at": review_payload.get("decided_at"),
        },
        "generation_run_id": _clean_string(
            payload.get("generation_run_id", ""), field_name="generation_run_id"
        ),
        "created_at": payload.get("created_at") or utc_now(),
        "updated_at": utc_now(),
        "accepted_at": payload.get("accepted_at"),
        "rejected_at": payload.get("rejected_at"),
        "superseded_at": payload.get("superseded_at"),
    }

    if normalized["input_snapshot"]["recipe_count"] < 0:
        raise ValueError("input_snapshot.recipe_count must be >= 0")

    if status == "accepted":
        if normalized["review"]["decision"] != "accepted":
            raise ValueError("accepted status requires review.decision=accepted")
        if not normalized["is_active"]:
            raise ValueError("accepted status requires is_active=true")
    elif status == "candidate_pending":
        if normalized["review"]["decision"] != "pending":
            raise ValueError(
                "candidate_pending status requires review.decision=pending"
            )
        if normalized["is_active"]:
            raise ValueError("candidate_pending status requires is_active=false")
    elif status == "rejected":
        if normalized["review"]["decision"] != "rejected":
            raise ValueError("rejected status requires review.decision=rejected")
        if normalized["is_active"]:
            raise ValueError("rejected status requires is_active=false")
    elif status == "superseded" and normalized["is_active"]:
        raise ValueError("superseded status requires is_active=false")

    return normalized
