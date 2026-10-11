# Taste Profiling Guide (How RecipeLab Learns Your Taste)

This guide explains **all current ways** you can influence AI recipe generation in RecipeLab, and the **effective weight/priority** each method has in code.

---

## 1) Influence Methods and Weights (At a Glance)

| Method | Where you set it | Effective weight | How it is used |
|---|---|---|---|
| **Meal type** (`main`, `lunch_batch`, etc.) | `/generate` or `POST /api/generate` | **Hard constraint** | Passed directly into prompt and normalized output; invalid types are rejected. |
| **Hard avoids** (`profile.hard_avoids`) | `/profile` | **Hard constraint (strict blocker)** | Inserted into prompt as **“hard avoids (strict)”** and explicitly required to be respected. |
| **Default hard avoids** (whole chickpeas, peanuts, sprouts, cauliflower, cinnamon) | Built-in fallback | **Hard constraint (strict blocker)** | Used only when profile hard_avoids is empty. |
| **Free-text generation instructions** | `/generate` instructions field or API `instructions` | **High soft influence** | Passed verbatim into prompt as `User instructions`. |
| **Profile likes/dislikes** | `/profile` | **Medium soft influence** | Added to prompt as preference context. |
| **Profile notes** | `/profile` | **Medium soft influence** | Added to prompt as extra context. |
| **Model selection** | `/settings` or API `model` override | **High model-behavior influence** | Changes model used for generation (style/compliance/quality can shift). |
| **Feedback: liked/disliked** | recipe/suggestion detail pages (`/feedback`) | **Indirect, medium after apply** | Used to generate profile update suggestions (token support scoring). |
| **Feedback: note** | recipe/suggestion detail pages (`/feedback`) | **No current automatic weight** | Stored/displayed, but not used by auto profile suggestion logic today. |
| **Apply/reject profile suggestions** | `/profile` suggestion actions | **Gatekeeper control** | Only **applied** suggestions update active likes/dislikes and affect future prompts. |

---

## 2) Direct Prompt Inputs (Immediate Effect on Next Generation)

Generation prompt is built by `compose_recipe_prompt()` and includes:

- `meal_type`
- `instructions`
- active profile: `likes`, `dislikes`, `hard_avoids`, `notes`
- explicit hard requirements (including strict hard avoids)

Code path:

- `app/services/generation_service.py` -> `generate_recipe_suggestion()`
- `app/services/prompt_composer.py` -> `compose_recipe_prompt()`

### Important behavior: hard-avoid fallback rule

- If profile `hard_avoids` is empty, RecipeLab uses built-in defaults:
  - whole chickpeas, peanuts, sprouts, cauliflower, cinnamon.
- If profile `hard_avoids` is non-empty, that list is used instead of fallback defaults.

So if you want both your custom avoids + defaults, include all of them in `/profile`.

---

## 3) Feedback-Driven Learning (Indirect Effect)

Feedback is saved to `feedback_events`, then processed when you run:

- **Generate Update Suggestions** on `/profile`

Code path:

- `app/services/profile_refinement_service.py` -> `generate_profile_update_suggestions()`

### How weighting works in this stage

This stage uses **support count** (frequency) per preference phrase:

- Candidates are extracted from recipe tags and normalized ingredient names. Ingredient phrases stay together (for example, `brown rice` rather than separate `brown` and `rice` candidates); preparation-only words such as `chopped` and `removed` are ignored.
- For each liked/disliked event, each distinct candidate phrase in that recipe counts once.
- Only phrases with `support_count >= min_support` are suggested (`min_support` default is `2`).
- Generating suggestions again replaces pending items that are no longer supported, so stale suggestions from older extraction logic are cleared from the pending list.
- Rejected and undone phrases are not suggested again unless reopened. Deleting a suggestion removes that suppression record, so supported feedback may produce it again later.
- Existing likes/dislikes/hard_avoids are excluded from new suggestions.

Then you decide:

- **Accept** -> writes the phrase into active `likes` or `dislikes` profile.
- **Edit an applied suggestion** -> changes its phrase/direction and updates the active profile immediately.
- **Undo an applied suggestion** -> removes its phrase from the active profile and moves it to undone history.
- **Reject** -> no profile change; the phrase can be edited or reopened later.
- **Delete** -> permanently removes the suggestion record. Deleting an applied item also removes its associated active preference.
- These actions are also available in bulk for selected suggestions in each status section.

So feedback has **no direct immediate prompt impact** until the suggestion is applied.

---

## 4) What Does *Not* Currently Influence Generation Automatically

- Editing saved recipes alone does not directly change prompt content.
- Feedback `note` signals are stored and shown, but not auto-scored for profile updates yet.
- `preferences.weights` exists in schema/storage but is not currently used in generation scoring.

---

## 5) Practical “Most Powerful” Workflow

1. Set accurate `hard_avoids`, `likes`, `dislikes`, and `notes` in `/profile`.
2. Use specific instructions in `/generate` (time, texture, protein, cuisine, constraints).
3. Give consistent liked/disliked feedback on outputs.
4. Run **Generate Update Suggestions** in `/profile`.
5. Apply only high-quality profile suggestions.
6. Re-test generation and refine profile iteratively.

---

## 6) Priority Stack (How to think about influence)

From strongest to weakest:

1. **Hard constraints** (meal type validity + hard avoids strict rule)
2. **User instructions** (explicit request for this run)
3. **Profile context** (likes/dislikes/notes)
4. **Model choice** (changes model behavior characteristics)
5. **Feedback history** (only after suggestion generation + apply)
6. **Stored notes/weights fields** (currently minimal/no automatic effect)

---

## 7) API Notes

`POST /api/generate` supports:

- `meal_type`
- `instructions`
- optional `model` override

API model override can supersede the UI-selected model for that request.
