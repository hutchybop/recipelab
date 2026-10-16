# New Profiling Phase 2 UI-Focused UAT Checklist - Service Integration Regression

Date: 16-Oct-26
Tester: hutch
Environment/Branch: .venv main
Mongo DB Name Used: RecipeLab

---

## 1) Preconditions

- [x] App is running at `http://localhost:3009`
- [x] `GET /api/health` responds successfully
- [x] Existing pages load before testing (`/`, `/recipes`, `/suggestions`, `/generate`, `/profile`)

---

## 2) Why this checklist is UI-focused

Phase 2 primarily adds backend/service logic for tasting-profile candidate generation.
Direct UI changes are expected to be minimal at this stage.

- [x] Confirm no unexpected UI behavior changes are introduced.
- [x] Confirm existing generation/import/profile pages remain usable.

---

## 3) Core Page Smoke Checks

- [x] `/` dashboard renders without errors
- [x] `/recipes` renders and recipe links open
- [x] `/suggestions` renders
- [x] `/generate` renders and shows existing form fields
- [x] `/import` renders and existing form works
- [x] `/profile` renders and existing controls still function for current phase baseline
- [x] `/settings` renders and model selection still saves

---

## 4) Existing UI Flow Regressions

- [x] Generate flow: `/generate` -> submit -> redirected to suggestion detail
- [x] Suggestion detail page renders correctly after generation
- [x] Import flow: `/import` -> submit -> redirected to suggestion detail
- [x] Accept suggestion flow still saves to recipe library
- [x] Recipe detail/edit pages still load and save successfully

---

## 5) Error-State UX Regression

- [x] Temporarily force LLM failure (e.g., invalid provider/model) and verify user still sees clear failure message.
- [x] Invalid meal type submission still shows a validation message.
- [x] No raw tracebacks or broken templates shown in browser.

---

## 6) Automated Regression Checks (UI-relevant)

Run:

```bash
.venv/bin/python -m unittest tests.test_web_routes -v
.venv/bin/python -m unittest tests.test_generate_api -v
.venv/bin/python -m unittest tests.test_prompt_composer tests.test_tasting_profile_service -v
.venv/bin/python -m unittest discover -s tests -v
```

- [x] Web route tests pass
- [x] Generate API tests pass
- [x] Prompt composer + tasting profile service tests pass
- [x] Full test suite passes

---

## 7) Validation Gate Decision

Gate requirement: no UI regressions while Phase 2 backend additions are in place.

Overall Result:
- [x] PASS - Phase 2 UI regression gate complete
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
