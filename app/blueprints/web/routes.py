from __future__ import annotations

import json

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from ...extensions import get_mongo_db
from ...repositories import (
    FeedbackEventsRepository,
    PreferencesRepository,
    RecipesRepository,
    RuntimeSettingsRepository,
    SuggestionsRepository,
    TastingProfilesRepository,
)
from ...services import (
    MEAL_TYPES,
    apply_profile_update_suggestion,
    bulk_manage_profile_update_suggestions,
    convert_raw_recipe_to_suggestion,
    delete_profile_update_suggestion,
    edit_profile_update_suggestion,
    get_allowed_models,
    get_effective_model,
    generate_recipe_suggestion,
    generate_tasting_profile_candidate,
    normalize_recipe_document,
    pdf_filename_for_recipe,
    reopen_profile_update_suggestion,
    reject_profile_update_suggestion,
    render_recipe_pdf,
    undo_profile_update_suggestion,
)


web_bp = Blueprint("web", __name__)


@web_bp.get("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder, "favicon/favicon.ico")


@web_bp.get("/site.webmanifest")
def webmanifest():
    return send_from_directory(current_app.static_folder, "favicon/site.webmanifest")


@web_bp.get("/browserconfig.xml")
def browserconfig():
    return send_from_directory(current_app.static_folder, "favicon/browserconfig.xml")


@web_bp.get("/")
def index() -> str:
    db = get_mongo_db()
    recipes_repo = RecipesRepository(db)
    suggestions_repo = SuggestionsRepository(db)

    recipes_count = len(recipes_repo.list(limit=500))
    draft_count = len(suggestions_repo.list_by_status("draft", limit=500))
    invalid_count = len(suggestions_repo.list_by_status("draft_invalid", limit=500))

    return render_template(
        "dashboard.html",
        recipes_count=recipes_count,
        draft_count=draft_count,
        invalid_count=invalid_count,
    )


@web_bp.route("/generate", methods=["GET", "POST"])
def generate_page() -> str:
    selected_meal_type = "main"
    instructions = ""
    db = get_mongo_db()

    if request.method == "POST":
        selected_meal_type = str(request.form.get("meal_type", "main")).strip()
        instructions = str(request.form.get("instructions", "")).strip()

        if selected_meal_type not in MEAL_TYPES:
            flash("Please select a valid meal type.", "danger")
            return redirect(url_for("web.generate_page"))

        try:
            result = generate_recipe_suggestion(
                db=db,
                meal_type=selected_meal_type,
                instructions=instructions,
            )
        except Exception:
            flash(
                "Generation is temporarily unavailable because the database connection failed. "
                "Please verify MongoDB Atlas connectivity and try again.",
                "danger",
            )
            return redirect(url_for("web.generate_page"))

        if not result.get("ok"):
            flash(result.get("error", "Generation failed."), "danger")
            return redirect(url_for("web.generate_page"))

        if result.get("status") == "draft":
            flash(
                "Recipe suggestion generated. Review and save it to your library.",
                "success",
            )
        else:
            flash(
                "Suggestion generated but marked draft_invalid. Review details before saving.",
                "warning",
            )

        return redirect(
            url_for("web.suggestion_detail", suggestion_id=result["suggestion_id"])
        )

    return render_template(
        "generate.html",
        meal_types=sorted(MEAL_TYPES),
        selected_meal_type=selected_meal_type,
        instructions=instructions,
        current_model=get_effective_model(db),
    )


@web_bp.get("/suggestions")
def suggestions_page() -> str:
    status = str(request.args.get("status", "draft")).strip()
    repo = SuggestionsRepository(get_mongo_db())

    if status == "all":
        suggestions = []
        for value in ["draft", "draft_invalid", "accepted", "rejected"]:
            suggestions.extend(repo.list_by_status(value, limit=200))
        suggestions = sorted(
            suggestions, key=lambda item: item.get("created_at"), reverse=True
        )
    else:
        suggestions = repo.list_by_status(status, limit=200)

    return render_template(
        "suggestions.html", suggestions=suggestions, selected_status=status
    )


@web_bp.get("/suggestions/<suggestion_id>")
def suggestion_detail(suggestion_id: str) -> str:
    db = get_mongo_db()
    suggestion = SuggestionsRepository(db).get_by_id(suggestion_id)
    if not suggestion:
        flash("Suggestion not found.", "warning")
        return redirect(url_for("web.suggestions_page"))

    feedback_repo = FeedbackEventsRepository(db)
    feedback_history = feedback_repo.list_for_target(
        target_type="suggestion", target_id=suggestion_id, limit=20
    )
    feedback_state = _feedback_state_from_events(feedback_history)
    return render_template(
        "suggestion_detail.html",
        suggestion=suggestion,
        feedback_state=feedback_state,
        feedback_history=feedback_history,
    )


@web_bp.route("/suggestions/<suggestion_id>/edit", methods=["GET", "POST"])
def edit_suggestion(suggestion_id: str):
    db = get_mongo_db()
    repo = SuggestionsRepository(db)
    recipes_repo = RecipesRepository(db)
    suggestion = repo.get_by_id(suggestion_id)
    if not suggestion:
        flash("Suggestion not found.", "warning")
        return redirect(url_for("web.suggestions_page"))

    if suggestion.get("status") not in {"draft", "draft_invalid"}:
        flash("Only draft suggestions can be edited.", "warning")
        return redirect(url_for("web.suggestion_detail", suggestion_id=suggestion_id))

    if request.method == "POST":
        meal_type = str(
            request.form.get("meal_type", suggestion.get("meal_type", "main"))
        ).strip()
        if meal_type not in MEAL_TYPES:
            flash("Please select a valid meal type.", "danger")
            return redirect(url_for("web.edit_suggestion", suggestion_id=suggestion_id))

        tags = _merge_tags_from_form(request.form)
        method = [
            item.strip()
            for item in str(request.form.get("method", "")).splitlines()
            if item.strip()
        ]
        notes = [
            item.strip()
            for item in str(request.form.get("notes", "")).splitlines()
            if item.strip()
        ]
        ingredients_lines = [
            item.strip()
            for item in str(request.form.get("ingredients", "")).splitlines()
            if item.strip()
        ]

        recipe_payload = {
            "title": str(request.form.get("title", "")).strip(),
            "meal_type": meal_type,
            "source_type": str(request.form.get("source_type", "user")).strip()
            or "user",
            "source": str(request.form.get("source", "")).strip(),
            "servings": str(request.form.get("servings", "")).strip(),
            "prep_time": str(request.form.get("prep_time", "")).strip(),
            "cook_time": str(request.form.get("cook_time", "")).strip(),
            "rating": str(request.form.get("rating", "")).strip(),
            "difficulty": str(request.form.get("difficulty", "")).strip(),
            "tags": tags,
            "ingredients": ingredients_lines,
            "method": method,
            "notes": notes,
        }

        try:
            normalized_recipe = normalize_recipe_document(recipe_payload)
            updated = repo.update_recipe_for_review(
                suggestion_id,
                title=recipe_payload["title"],
                meal_type=meal_type,
                recipe=normalized_recipe,
            )
        except Exception as exc:
            flash(f"Could not update suggestion: {exc}", "danger")
            return redirect(url_for("web.edit_suggestion", suggestion_id=suggestion_id))

        if updated:
            flash("Suggestion updated. Review and save when ready.", "success")
        else:
            flash("No changes were saved.", "warning")
        return redirect(url_for("web.suggestion_detail", suggestion_id=suggestion_id))

    selected_tags = _normalize_tag_values(
        suggestion.get("recipe", {}).get("metadata", {}).get("tags", [])
    )
    available_tags = _merge_available_tags(recipes_repo.list_all_tags(), selected_tags)

    return render_template(
        "suggestion_edit.html",
        suggestion=suggestion,
        meal_types=sorted(MEAL_TYPES),
        available_tags=available_tags,
        selected_tags=selected_tags,
    )


@web_bp.post("/suggestions/<suggestion_id>/accept")
def accept_suggestion(suggestion_id: str):
    db = get_mongo_db()
    suggestions_repo = SuggestionsRepository(db)
    recipes_repo = RecipesRepository(db)

    suggestion = suggestions_repo.get_by_id(suggestion_id)
    if not suggestion:
        flash("Suggestion not found.", "warning")
        return redirect(url_for("web.suggestions_page"))

    if suggestion.get("status") != "draft":
        flash("Only draft suggestions can be saved.", "warning")
        return redirect(url_for("web.suggestion_detail", suggestion_id=suggestion_id))

    payload = suggestion.get("recipe", {})
    metadata = payload.get("metadata", {})

    try:
        recipe = recipes_repo.create(
            {
                "title": payload.get("title", suggestion.get("title", "Untitled")),
                "meal_type": payload.get(
                    "meal_type", suggestion.get("meal_type", "main")
                ),
                "source_type": payload.get("source_type", "ai"),
                "source": metadata.get("source", "AI Generated"),
                "servings": metadata.get("servings", ""),
                "prep_time": metadata.get("prep_time", ""),
                "cook_time": metadata.get("cook_time", ""),
                "rating": metadata.get("rating", ""),
                "difficulty": metadata.get("difficulty", ""),
                "tags": metadata.get("tags", []),
                "ingredients": payload.get("ingredients", []),
                "method": payload.get("method", []),
                "notes": payload.get("notes", []),
            }
        )
    except Exception:
        flash(
            "Could not save this suggestion due to a database constraint. Please try again.",
            "danger",
        )
        return redirect(url_for("web.suggestion_detail", suggestion_id=suggestion_id))

    suggestions_repo.update_status(suggestion_id, "accepted")
    flash("Suggestion saved to recipe library.", "success")
    return redirect(url_for("web.recipe_detail", recipe_id=str(recipe["_id"])))


@web_bp.post("/suggestions/<suggestion_id>/reject")
def reject_suggestion(suggestion_id: str):
    updated = SuggestionsRepository(get_mongo_db()).update_status(
        suggestion_id, "rejected"
    )
    if updated:
        flash("Suggestion rejected.", "info")
    else:
        flash("Suggestion not found.", "warning")
    return redirect(url_for("web.suggestions_page"))


@web_bp.get("/recipes")
def recipes_page() -> str:
    selected_meal_type = str(request.args.get("meal_type", "")).strip()
    if selected_meal_type and selected_meal_type not in MEAL_TYPES:
        selected_meal_type = ""
        flash("Invalid meal type filter ignored.", "warning")

    db = get_mongo_db()
    recipes = RecipesRepository(db).list(
        meal_type=selected_meal_type or None, limit=300
    )
    recipe_ids = [str(recipe["_id"]) for recipe in recipes]
    feedback_by_recipe: dict[str, list[dict]] = {
        recipe_id: [] for recipe_id in recipe_ids
    }
    for event in FeedbackEventsRepository(db).list_for_targets(
        target_type="recipe", target_ids=recipe_ids
    ):
        feedback_by_recipe.setdefault(str(event.get("target_id", "")), []).append(event)
    feedback_states = {
        recipe_id: _feedback_state_from_events(events)
        for recipe_id, events in feedback_by_recipe.items()
    }
    return render_template(
        "recipes.html",
        recipes=recipes,
        feedback_states=feedback_states,
        meal_types=sorted(MEAL_TYPES),
        selected_meal_type=selected_meal_type,
    )


@web_bp.route("/import", methods=["GET", "POST"])
def import_recipe_page() -> str:
    selected_meal_type = "main"
    raw_recipe_text = ""
    db = get_mongo_db()

    if request.method == "POST":
        selected_meal_type = str(request.form.get("meal_type", "main")).strip()
        raw_recipe_text = str(request.form.get("raw_recipe_text", "")).strip()

        if selected_meal_type not in MEAL_TYPES:
            flash("Please select a valid meal type.", "danger")
            return redirect(url_for("web.import_recipe_page"))

        if not raw_recipe_text:
            flash("Please paste a raw recipe to convert.", "warning")
            return redirect(url_for("web.import_recipe_page"))

        try:
            result = convert_raw_recipe_to_suggestion(
                db=db,
                meal_type=selected_meal_type,
                raw_recipe_text=raw_recipe_text,
            )
        except Exception:
            flash(
                "Recipe conversion is temporarily unavailable because the database connection failed.",
                "danger",
            )
            return redirect(url_for("web.import_recipe_page"))

        if not result.get("ok"):
            flash(result.get("error", "Conversion failed."), "danger")
            return redirect(url_for("web.import_recipe_page"))

        if result.get("status") == "draft":
            flash(
                "Raw recipe converted. Review and save it to your library.", "success"
            )
        else:
            flash(
                "Converted output failed validation. Review and edit before saving.",
                "warning",
            )

        return redirect(
            url_for("web.suggestion_detail", suggestion_id=result["suggestion_id"])
        )

    return render_template(
        "import_recipe.html",
        meal_types=sorted(MEAL_TYPES),
        selected_meal_type=selected_meal_type,
        raw_recipe_text=raw_recipe_text,
        current_model=get_effective_model(db),
    )


@web_bp.route("/settings", methods=["GET", "POST"])
def settings_page() -> str:
    db = get_mongo_db()
    settings_repo = RuntimeSettingsRepository(db)
    allowed_models = get_allowed_models()

    if request.method == "POST":
        selected_model = str(request.form.get("model", "")).strip()
        if selected_model not in allowed_models:
            flash("Invalid model selection.", "danger")
            return redirect(url_for("web.settings_page"))
        settings_repo.set_selected_model(selected_model)
        flash("Runtime model updated.", "success")
        return redirect(url_for("web.settings_page"))

    current_model = get_effective_model(db)
    provider = str(current_app.config.get("LLM_PROVIDER", "")).strip()
    endpoint = str(current_app.config.get("LLM_ENDPOINT", "")).strip()

    return render_template(
        "settings.html",
        allowed_models=allowed_models,
        current_model=current_model,
        provider=provider,
        endpoint=endpoint,
    )


@web_bp.get("/recipes/<recipe_id>")
def recipe_detail(recipe_id: str) -> str:
    db = get_mongo_db()
    recipe = RecipesRepository(db).get_by_id(recipe_id)
    if not recipe or recipe.get("deleted_at") is not None:
        flash("Recipe not found.", "warning")
        return redirect(url_for("web.recipes_page"))

    feedback_repo = FeedbackEventsRepository(db)
    feedback_history = feedback_repo.list_for_target(
        target_type="recipe", target_id=recipe_id, limit=20
    )
    feedback_state = _feedback_state_from_events(feedback_history)

    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        feedback_state=feedback_state,
        feedback_history=feedback_history,
    )


@web_bp.get("/recipes/<recipe_id>/pdf")
def export_recipe_pdf(recipe_id: str):
    db = get_mongo_db()
    recipe = RecipesRepository(db).get_by_id(recipe_id)
    if not recipe or recipe.get("deleted_at") is not None:
        flash("Recipe not found.", "warning")
        return redirect(url_for("web.recipes_page"))

    pdf_bytes = render_recipe_pdf(recipe)
    filename = pdf_filename_for_recipe(recipe)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@web_bp.post("/feedback")
def submit_feedback():
    target_type = str(request.form.get("target_type", "")).strip()
    target_id = str(request.form.get("target_id", "")).strip()
    signal = str(request.form.get("signal", "")).strip()
    notes = str(request.form.get("notes", "")).strip()
    return_to = str(request.form.get("return_to", "")).strip() or url_for("web.index")

    if target_type not in {"recipe", "suggestion"}:
        flash("Invalid feedback target.", "danger")
        return redirect(return_to)
    if signal not in {"liked", "disliked", "note"}:
        flash("Invalid feedback signal.", "danger")
        return redirect(return_to)

    feedback_repo = FeedbackEventsRepository(get_mongo_db())
    if signal in {"liked", "disliked"}:
        feedback_repo.delete_reactions_for_target(
            target_type=target_type,
            target_id=target_id,
        )

    feedback_repo.create(
        {
            "target_type": target_type,
            "target_id": target_id,
            "signal": signal,
            "notes": notes,
        }
    )
    flash("Feedback saved.", "success")
    return redirect(return_to)


@web_bp.post("/feedback/clear-reaction")
def clear_feedback_reaction():
    target_type = str(request.form.get("target_type", "")).strip()
    target_id = str(request.form.get("target_id", "")).strip()
    return_to = str(request.form.get("return_to", "")).strip() or url_for("web.index")

    if target_type not in {"recipe", "suggestion"} or not target_id:
        flash("Invalid feedback target.", "danger")
        return redirect(return_to)

    deleted = FeedbackEventsRepository(get_mongo_db()).delete_reactions_for_target(
        target_type=target_type,
        target_id=target_id,
    )
    flash(
        "Reaction cleared." if deleted else "No reaction to clear.",
        "info",
    )
    return redirect(return_to)


@web_bp.post("/feedback/clear-note")
def clear_feedback_note():
    target_type = str(request.form.get("target_type", "")).strip()
    target_id = str(request.form.get("target_id", "")).strip()
    return_to = str(request.form.get("return_to", "")).strip() or url_for("web.index")

    if target_type not in {"recipe", "suggestion"} or not target_id:
        flash("Invalid feedback target.", "danger")
        return redirect(return_to)

    changed = FeedbackEventsRepository(get_mongo_db()).clear_notes_for_target(
        target_type=target_type,
        target_id=target_id,
    )
    flash(
        "Note deleted." if changed else "No note to delete.",
        "info",
    )
    return redirect(return_to)


@web_bp.route("/profile", methods=["GET", "POST"])
def profile_page() -> str:
    db = get_mongo_db()
    preferences_repo = PreferencesRepository(db)
    tasting_profiles_repo = TastingProfilesRepository(db)

    active_profile = preferences_repo.get_active_profile() or {
        "profile_name": "default",
        "active": True,
        "hard_avoids": [],
        "dislikes": [],
        "weights": {},
    }

    if request.method == "POST":
        action = str(request.form.get("action", "save_profile")).strip()

        if action == "save_profile":
            hard_avoids = [
                item.strip()
                for item in str(request.form.get("hard_avoids", "")).splitlines()
                if item.strip()
            ]
            dislikes = [
                item.strip()
                for item in str(request.form.get("dislikes", "")).splitlines()
                if item.strip()
            ]

            preferences_repo.upsert_profile(
                {
                    "profile_name": str(active_profile.get("profile_name", "default"))
                    or "default",
                    "active": True,
                    "hard_avoids": hard_avoids,
                    "likes": [],
                    "dislikes": dislikes,
                    "notes": "",
                    "weights": active_profile.get("weights", {}),
                }
            )
            flash("Profile updated.", "success")
            return redirect(url_for("web.profile_page"))

        if action in {"generate_tasting_profile", "regenerate_tasting_profile"}:
            result = generate_tasting_profile_candidate(db=db)
            if result.get("ok"):
                flash(
                    "Tasting profile candidate generated. Review and accept or reject it.",
                    "success",
                )
            else:
                flash(
                    result.get("error", "Could not generate tasting profile."), "danger"
                )
            return redirect(url_for("web.profile_page"))

    active_profile = preferences_repo.get_active_profile() or active_profile
    active_tasting_profile = tasting_profiles_repo.get_active_profile()
    latest_candidate = tasting_profiles_repo.get_latest_candidate()

    active_tasting_profile_json = (
        json.dumps(
            active_tasting_profile.get("profile", {}), indent=2, ensure_ascii=False
        )
        if active_tasting_profile
        else ""
    )
    latest_candidate_json = (
        json.dumps(latest_candidate.get("profile", {}), indent=2, ensure_ascii=False)
        if latest_candidate
        else ""
    )

    return render_template(
        "profile.html",
        profile=active_profile,
        active_tasting_profile=active_tasting_profile,
        latest_candidate=latest_candidate,
        active_tasting_profile_json=active_tasting_profile_json,
        latest_candidate_json=latest_candidate_json,
    )


@web_bp.post("/profile/tasting-profiles/<profile_id>/accept")
def accept_tasting_profile(profile_id: str):
    accepted = TastingProfilesRepository(get_mongo_db()).accept_candidate(profile_id)
    flash(
        (
            "Tasting profile accepted and set active."
            if accepted
            else "Candidate tasting profile not found or no longer pending."
        ),
        "success" if accepted else "warning",
    )
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/tasting-profiles/<profile_id>/reject")
def reject_tasting_profile(profile_id: str):
    rejected = TastingProfilesRepository(get_mongo_db()).reject_candidate(profile_id)
    flash(
        (
            "Tasting profile candidate rejected."
            if rejected
            else "Candidate tasting profile not found or no longer pending."
        ),
        "info" if rejected else "warning",
    )
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/suggestions/<suggestion_id>/apply")
def apply_profile_suggestion(suggestion_id: str):
    ok, message = apply_profile_update_suggestion(get_mongo_db(), suggestion_id)
    flash(message, "success" if ok else "warning")
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/suggestions/<suggestion_id>/reject")
def reject_profile_suggestion(suggestion_id: str):
    updated = reject_profile_update_suggestion(get_mongo_db(), suggestion_id)
    flash(
        "Suggestion rejected." if updated else "Suggestion not found.",
        "info" if updated else "warning",
    )
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/suggestions/<suggestion_id>/edit")
def edit_profile_suggestion(suggestion_id: str):
    ok, message = edit_profile_update_suggestion(
        get_mongo_db(),
        suggestion_id,
        action=str(request.form.get("suggestion_action", "")),
        token=str(request.form.get("token", "")),
    )
    flash(message, "success" if ok else "warning")
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/suggestions/bulk")
def bulk_profile_suggestions():
    suggestion_ids = request.form.getlist("suggestion_ids")
    operation = str(request.form.get("bulk_action", "")).strip()
    if not suggestion_ids:
        flash("Select at least one suggestion first.", "warning")
        return redirect(url_for("web.profile_page"))

    if operation not in {"accept", "reject", "reopen", "undo", "delete"}:
        flash("Choose a valid bulk action.", "warning")
        return redirect(url_for("web.profile_page"))

    results = bulk_manage_profile_update_suggestions(
        get_mongo_db(), suggestion_ids, operation=operation
    )
    flash(
        f"Bulk action complete: {results['updated']} updated, "
        f"{results['deleted']} deleted, {results['skipped']} skipped.",
        "info",
    )
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/suggestions/<suggestion_id>/undo")
def undo_profile_suggestion(suggestion_id: str):
    ok, message = undo_profile_update_suggestion(get_mongo_db(), suggestion_id)
    flash(message, "info" if ok else "warning")
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/suggestions/<suggestion_id>/reopen")
def reopen_profile_suggestion(suggestion_id: str):
    updated = reopen_profile_update_suggestion(get_mongo_db(), suggestion_id)
    flash(
        (
            "Suggestion reopened as pending."
            if updated
            else "Suggestion cannot be reopened."
        ),
        "info" if updated else "warning",
    )
    return redirect(url_for("web.profile_page"))


@web_bp.post("/profile/suggestions/<suggestion_id>/delete")
def delete_profile_suggestion(suggestion_id: str):
    ok, message = delete_profile_update_suggestion(get_mongo_db(), suggestion_id)
    flash(message, "info" if ok else "warning")
    return redirect(url_for("web.profile_page"))


@web_bp.route("/recipes/<recipe_id>/edit", methods=["GET", "POST"])
def edit_recipe(recipe_id: str):
    repo = RecipesRepository(get_mongo_db())
    recipe = repo.get_by_id(recipe_id)
    if not recipe or recipe.get("deleted_at") is not None:
        flash("Recipe not found.", "warning")
        return redirect(url_for("web.recipes_page"))

    if request.method == "POST":
        meal_type = str(
            request.form.get("meal_type", recipe.get("meal_type", "main"))
        ).strip()
        if meal_type not in MEAL_TYPES:
            flash("Please select a valid meal type.", "danger")
            return redirect(url_for("web.edit_recipe", recipe_id=recipe_id))

        tags = _merge_tags_from_form(request.form)
        method = [
            item.strip()
            for item in str(request.form.get("method", "")).splitlines()
            if item.strip()
        ]
        notes = [
            item.strip()
            for item in str(request.form.get("notes", "")).splitlines()
            if item.strip()
        ]

        ingredients_lines = [
            item.strip()
            for item in str(request.form.get("ingredients", "")).splitlines()
            if item.strip()
        ]

        update_fields = {
            "title": str(request.form.get("title", "")).strip(),
            "meal_type": meal_type,
            "source_type": str(
                request.form.get("source_type", recipe.get("source_type", "user"))
            ).strip()
            or "user",
            "ingredients": ingredients_lines,
            "method": method,
            "notes": notes,
            "source": str(request.form.get("source", "")).strip(),
            "servings": str(request.form.get("servings", "")).strip(),
            "prep_time": str(request.form.get("prep_time", "")).strip(),
            "cook_time": str(request.form.get("cook_time", "")).strip(),
            "rating": str(request.form.get("rating", "")).strip(),
            "difficulty": str(request.form.get("difficulty", "")).strip(),
            "tags": tags,
        }

        try:
            updated = repo.update(recipe_id, update_fields)
        except Exception as exc:
            flash(f"Could not update recipe: {exc}", "danger")
            return redirect(url_for("web.edit_recipe", recipe_id=recipe_id))

        if updated:
            flash("Recipe updated.", "success")
        else:
            flash("No changes were saved.", "warning")
        return redirect(url_for("web.recipe_detail", recipe_id=recipe_id))

    selected_tags = _normalize_tag_values(recipe.get("metadata", {}).get("tags", []))
    available_tags = _merge_available_tags(repo.list_all_tags(), selected_tags)

    return render_template(
        "recipe_edit.html",
        recipe=recipe,
        meal_types=sorted(MEAL_TYPES),
        available_tags=available_tags,
        selected_tags=selected_tags,
    )


@web_bp.post("/recipes/<recipe_id>/delete")
def delete_recipe(recipe_id: str):
    deleted = RecipesRepository(get_mongo_db()).delete(recipe_id)
    if deleted:
        flash("Recipe permanently deleted.", "info")
    else:
        flash("Recipe not found.", "warning")
    return redirect(url_for("web.recipes_page"))


def _merge_tags_from_form(form_data) -> list[str]:
    selected_tags = form_data.getlist("tags_selected")
    manual_tags = _split_tag_text(str(form_data.get("new_tags", "")))
    legacy_tags = _split_tag_text(str(form_data.get("tags", "")))
    return _normalize_tag_values([*selected_tags, *manual_tags, *legacy_tags])


def _split_tag_text(raw: str) -> list[str]:
    normalized = raw.replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _normalize_tag_values(values) -> list[str]:
    if values is None:
        return []

    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)

    return output


def _merge_available_tags(
    existing_tags: list[str], selected_tags: list[str]
) -> list[str]:
    return sorted(set(existing_tags) | set(selected_tags))


def _feedback_state_from_events(events: list[dict]) -> dict[str, str]:
    reaction = ""
    reaction_at = ""
    latest_note = ""
    latest_note_at = ""

    for event in events:
        signal = str(event.get("signal", ""))
        notes = str(event.get("notes", "")).strip()
        created_at = str(event.get("created_at", ""))

        if not reaction and signal in {"liked", "disliked"}:
            reaction = signal
            reaction_at = created_at

        if not latest_note and notes:
            latest_note = notes
            latest_note_at = created_at

        if reaction and latest_note:
            break

    return {
        "reaction": reaction,
        "reaction_at": reaction_at,
        "latest_note": latest_note,
        "latest_note_at": latest_note_at,
    }
