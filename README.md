# RecipeLab

RecipeLab is an **AI-powered recipe studio**: it helps you turn your existing recipe library and tasting profile into smarter, personalized recipe suggestions.

Import what you already cook, define dislikes and hard avoids, then generate recipes aligned to your preferences.

## Why RecipeLab

- **Personalized AI generation** based on your active tasting profile
- **Library-first workflow**: keep and improve your own recipe collection
- **Profile lifecycle**: generate, review, and accept AI tasting profile candidates
- **Practical output**: normalized ingredients + clear methods, ready to save/edit/export

## Features

- Recipe dashboard and browser (`/`, `/recipes`)
- Recipe CRUD flows (view, edit, delete)
- AI suggestion generation (`/generate`, `POST /api/generate`) with profile-aware prompts
- Raw recipe conversion/import flow (`/import`)
- Suggestion review workflow (draft / draft_invalid / accepted / rejected)
- Tasting profile workflow (`/profile`): save inputs, generate/regenerate candidate, accept/reject
- Runtime model selection (`/settings`)
- PDF export for recipes (`/recipes/<id>/pdf`)
- Responsive web UI for phone/tablet/laptop/desktop screen sizes
- Accessibility polish: skip-link navigation, clear keyboard focus states, and active-nav orientation
- Health endpoint (`GET /api/health`)

## Tech Stack

- Python 3.12+
- Flask
- PyMongo (MongoDB)
- OpenAI SDK (OpenAI-compatible endpoint support)
- Gunicorn
- Black + Flake8

## Project Structure

```text
app/
  blueprints/      # Web + API routes
  repositories/    # MongoDB data access + indexes
  services/        # Generation, prompts, schema normalization, PDF export
  templates/       # Jinja templates
  config.py        # Env config + validation
  extensions.py    # Mongo client/db wiring
docs/              # Project docs
recipes/           # Markdown recipe library
scripts/           # Import utilities
tests/             # unittest suite
run.py             # App entrypoint (run:app)
```

## Prerequisites

- Python 3.12+
- MongoDB instance (Atlas or local)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Create local env file:

```bash
cp .env.example .env
```

Required at startup:

- `SECRET_KEY`
- `MONGO_URI`

Notes:

- `MONGO_DB_NAME` defaults to `recipelab` if not set.
- LLM features require provider/model vars (`LLM_PROVIDER`, `LLM_MODEL`, optional `LLM_ALLOWED_MODELS`, etc.).

## AI Setup (Recommended)

RecipeLab’s core value is AI-generated recipes tailored to your profile. Configure these in `.env`:

```env
LLM_PROVIDER=openai_compatible
LLM_ENDPOINT=https://opencode.ai/zen/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-5.4
LLM_ALLOWED_MODELS=gpt-5.4,deepseek-v4.1-flash
```

Then:

1. Start the app and open `/settings` to confirm/select the runtime model.
2. Open `/profile` and set dislikes + hard avoids, then generate and accept a tasting profile candidate.
3. (Optional) Import your recipe markdown library into MongoDB so your collection is in-app:

   ```bash
   python scripts/import_markdown_recipes.py
   ```

4. Generate from `/generate` (or `POST /api/generate`).

> Notes:
>
> - Generation requires an **accepted tasting profile**.
> - Optional `reference_recipe_ids` (up to 4) can be passed from UI/API as style/taste anchors.

## Run Locally

```bash
python run.py
```

App binds to `0.0.0.0:3009`.

## Run with Docker

```bash
docker compose up --build
```

Serves on `http://localhost:3009` (`3009:3009` in compose, env loaded from `.env`).

## Smoke Check

- Open `http://localhost:3009/`
- Check health:

```bash
curl -i http://localhost:3009/api/health
```

Quick AI check:

> Requires an accepted tasting profile; otherwise this returns `409`.

```bash
curl -i http://localhost:3009/api/generate \
  -H "Content-Type: application/json" \
  -d '{"meal_type":"main","instructions":"high-protein dinner under 40 minutes"}'
```

## API

### `GET /api/health`

Returns service health. If Mongo ping fails, returns `503` with `status: degraded`.

### `POST /api/generate`

Request:

```json
{
  "meal_type": "main",
  "instructions": "high-protein dinner",
  "model": "optional-model-override",
  "reference_recipe_ids": ["optional_recipe_id_1", "optional_recipe_id_2"]
}
```

Valid `meal_type` values:

- `main`
- `lunch_batch`
- `lunch_single`
- `breakfast`
- `dessert`

Response:

- `201` for valid draft suggestion
- `422` for `draft_invalid`
- `400` for invalid meal type
- `409` when no accepted tasting profile exists
- `502` when LLM provider/model generation fails
- `503` if backend/database is unavailable

## Import Existing Markdown Recipes

Use the import script:

```bash
python scripts/import_markdown_recipes.py
```

Useful flags:

- `--recipes-dir recipes`
- `--exclude-dir "AI-suggested"` (repeatable)
- `--dry-run`

Notes:

- `recipes/tasting-profile.md` is automatically excluded by the importer.

## Tests

Run all tests:

```bash
python -m unittest discover -s tests
```

Manual UAT checklists are in `docs/checklists/` (including responsive UI validation checklists for phases 9, 10, and 11).

## Additional Guides

- Taste profiling and influence weights: `docs/taste-profiling.md`

## Lint / Format

```bash
flake8 .
black .
```

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE).
