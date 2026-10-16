from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...extensions import mongo_health
from ...extensions import get_mongo_db
from ...services import MEAL_TYPES, generate_recipe_suggestion


api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health_check():
    mongo_ok, error_message = mongo_health()
    payload = {
        "status": "ok" if mongo_ok else "degraded",
        "services": {
            "api": "ok",
            "mongo": "ok" if mongo_ok else "error",
        },
    }
    if error_message:
        payload["services"]["mongo_error"] = error_message
    status_code = 200 if mongo_ok else 503
    return jsonify(payload), status_code


@api_bp.post("/generate")
def generate_recipe():
    payload = request.get_json(silent=True) or {}
    meal_type = str(payload.get("meal_type", "")).strip()
    instructions = str(payload.get("instructions", "")).strip()
    model_override = payload.get("model")
    reference_recipe_ids_payload = payload.get("reference_recipe_ids")
    reference_recipe_ids = (
        [
            str(item).strip()
            for item in reference_recipe_ids_payload
            if isinstance(item, str) and str(item).strip()
        ]
        if isinstance(reference_recipe_ids_payload, list)
        else []
    )

    if meal_type not in MEAL_TYPES:
        return (
            jsonify(
                {
                    "error": "Invalid meal_type",
                    "allowed_meal_types": sorted(MEAL_TYPES),
                }
            ),
            400,
        )

    try:
        result = generate_recipe_suggestion(
            db=get_mongo_db(),
            meal_type=meal_type,
            instructions=instructions,
            model_override=(
                str(model_override).strip() if isinstance(model_override, str) else None
            ),
            selected_recipe_ids=reference_recipe_ids,
        )
    except Exception:
        return (
            jsonify(
                {
                    "error": "Generation is temporarily unavailable because the database connection failed.",
                    "run_id": None,
                }
            ),
            503,
        )

    if not result["ok"]:
        status_code = int(result.get("status_code", 500))
        response = {
            "error": result.get("error", "Unknown generation error"),
            "run_id": result.get("run_id"),
        }
        return jsonify(response), status_code

    response_payload = {
        "status": result["status"],
        "run_id": result["run_id"],
        "suggestion_id": result["suggestion_id"],
        "validation": result["validation"],
        "recipe": result["recipe"],
    }
    return jsonify(response_payload), int(result["status_code"])
