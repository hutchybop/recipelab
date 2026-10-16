# New Profiling Phase 4 UAT Checklist - Generation Gate + Reference Recipes

Date: 16-Oct-26
Tester: hutch
Environment/Branch: .venv main
Mongo DB Name Used: RecipeLab

---

## 1) Preconditions

- [x] App is running at `http://localhost:3009`
- [x] `GET /api/health` responds successfully
- [x] At least 5 recipes exist in the recipe library

---

## 2) Generation Gate (Accepted Profile Required)

- [x] With **no accepted tasting profile**, `/generate` shows a warning to create/accept one in `/profile`
- [x] Generate button is disabled when no accepted profile exists
- [x] API `POST /api/generate` without accepted profile returns clear error and non-2xx status
- [x] After accepting a tasting profile, `/generate` no longer shows blocking warning

---

## 3) Reference Recipe Selector (0..4)

- [x] `/generate` shows optional reference-recipe selector
- [x] Selector supports multiple choices with checkbox-style selection
- [x] Submit with 0 selected recipes succeeds
- [x] Submit with 1 selected recipe succeeds
- [x] Submit with 4 selected recipes succeeds
- [x] Submit with 5 selected recipes is blocked with a clear validation message

---

## 4) End-to-End Generate Flow

- [x] Generate with no instructions and no references -> suggestion created
- [x] Generate with instructions and references -> suggestion created
- [x] Redirect lands on suggestion detail page
- [x] Suggestion can still be accepted into recipe library

---

## 5) API Checks

- [x] `POST /api/generate` accepts optional `reference_recipe_ids`
- [x] API request with >4 `reference_recipe_ids` returns validation error
- [x] API request with valid `reference_recipe_ids` returns draft/draft_invalid payload as expected

---

## 6) Regression Checks

- [x] Import flow still works (`/import`)
- [x] Suggestions list/detail still renders correctly
- [x] Settings model selection still works

---

## 7) Automated Regression Checks

Run:

```bash
.venv/bin/python -m unittest tests.test_generate_api tests.test_runtime_settings tests.test_web_routes -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall app tests run.py
.venv/bin/python -m flake8 app tests
```

- [x] Targeted route/API tests pass
- [x] Full test suite passes
- [x] Compile check passes
- [x] Lint check passes

---

## 8) Validation Gate Decision

Gate requirement: generation is profile-gated and supports optional 0..4 reference recipes without regressions.

Overall Result:
- [x] PASS - Phase 4 complete
- [ ] FAIL - remediation required

Notes / Issues Found:

```

```

Remediation Tasks (if any):

```

```

Sign-off:
- Name: Hutch
- Date: 16-Oct-26
