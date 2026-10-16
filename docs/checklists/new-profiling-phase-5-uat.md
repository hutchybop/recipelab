# New Profiling Phase 5 UAT Checklist - Legacy Feedback/Profile-Suggestion Removal

Date: 16-Oct-26
Tester: hutch
Environment/Branch: .venv main
Mongo DB Name Used: RecipeLab

---

## 1) Preconditions

- [x] App is running at `http://localhost:3009`
- [x] `GET /api/health` responds successfully
- [x] Existing recipe and suggestion records are available to view detail pages

---

## 2) Feedback UI/Route Removal

- [x] Recipe detail page no longer shows Feedback controls/section
- [x] Suggestion detail page no longer shows Feedback controls/section
- [x] Recipe list no longer shows Liked/Disliked/Note badges
- [x] `POST /feedback` returns 404
- [x] `POST /feedback/clear-reaction` returns 404
- [x] `POST /feedback/clear-note` returns 404

---

## 3) Profile Suggestion Lifecycle Removal

- [x] `/profile` no longer shows pending/applied/rejected/undone suggestion sections
- [x] `/profile` no longer shows controls for suggestion edit/reopen/delete/bulk actions
- [x] `POST /profile/suggestions/<id>/apply` returns 404
- [x] `POST /profile/suggestions/<id>/reject` returns 404
- [x] `POST /profile/suggestions/<id>/edit` returns 404
- [x] `POST /profile/suggestions/<id>/undo` returns 404
- [x] `POST /profile/suggestions/<id>/reopen` returns 404
- [x] `POST /profile/suggestions/<id>/delete` returns 404
- [x] `POST /profile/suggestions/bulk` returns 404

---

## 4) New Profiling Flow Still Works

- [x] `/profile` still supports saving dislikes + hard avoids
- [x] Generate tasting profile candidate still works
- [x] Accept/reject tasting profile candidate still works
- [x] `/generate` gating and reference recipe behavior remain intact

---

## 5) Regression Checks

- [x] `/recipes` list/detail/edit still work
- [x] `/suggestions` list/detail/edit/accept/reject still work
- [x] `/import` flow still works
- [x] `/settings` still works

---

## 6) Automated Regression Checks

Run:

```bash
.venv/bin/python -m unittest tests.test_web_routes tests.test_indexes -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall app tests run.py
.venv/bin/python -m flake8 app tests
```

- [x] Web route + index tests pass
- [x] Full test suite passes
- [x] Compile check passes
- [x] Lint check passes

---

## 7) Validation Gate Decision

Gate requirement: legacy feedback/profile-suggestion paths are removed from active UX and routing, with core app flows still healthy.

Overall Result:
- [x] PASS - Phase 5 complete
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
