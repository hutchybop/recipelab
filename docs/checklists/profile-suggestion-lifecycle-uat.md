# Profile Suggestion Lifecycle UAT Checklist

Date: 26-10-10
Tester: hutch
Environment/Branch: .venv main 
Mongo DB Name Used: RecipeLab

---

## 1) Preconditions

- [x] App is running and `/profile` loads successfully.
- [] Use a test profile or record the existing Likes and Dislikes before testing.
- [x] Ensure there is at least one pending, applied, and rejected suggestion; create test feedback if needed.
- [x] Confirm the active profile and suggestion records can be inspected in the configured MongoDB database.

---

## 2) Pending Suggestions

- [x] Pending suggestions show editable Like/Dislike and phrase fields.
- [x] Edit a pending suggestion and save; verify its action and phrase change while its status remains pending.
- [x] Accept a pending like; verify it moves to Applied and appears in the profile Likes field.
- [x] Accept a pending dislike; verify it moves to Applied and appears in the profile Dislikes field.
- [x] Reject a pending suggestion; verify it moves to Rejected and does not change the active profile.
- [x] Delete a pending suggestion and confirm; verify it is removed from the database and the UI.

---

## 3) Applied Suggestions and Prompt Effects

- [x] Edit an applied like's phrase; verify the active profile's Likes value changes and the suggestion remains Applied.
- [x] Change an applied like to a dislike; verify it is removed from Likes and added to Dislikes.
- [x] Change an applied dislike to a like; verify it is removed from Dislikes and added to Likes.
- [x] Generate a recipe after editing; verify the active profile values are the values supplied to the generation prompt (preferences guide softly; hard avoids remain strict).
- [x] Undo an applied suggestion and confirm; verify its matching profile value is removed and the record moves to Undone Suggestions.
- [x] Delete an applied suggestion and confirm; verify the record is permanently removed and its matching active profile value is removed.
- [x] Confirm an unrelated hard avoid, note, and other profile preferences remain unchanged after edits, undo, and delete.

---

## 4) Rejected and Undone Suggestions

- [x] Edit a rejected suggestion; verify the record remains Rejected and the active profile is unchanged.
- [x] Reopen a rejected suggestion; verify it returns to Pending without changing the active profile.
- [x] Edit an undone suggestion; verify it remains Undone and the active profile is unchanged.
- [x] Reopen an undone suggestion, accept it, and verify its preference is applied again.
- [x] With supported feedback present, generate suggestions and verify an unchanged rejected/undone action+phrase is suppressed.
- [x] Reopen that suggestion and generate again; verify it can be reviewed as pending.
- [x] Delete a rejected or undone suggestion; verify it is permanently removed from history.
- [x] If feedback still supports a deleted suggestion, verify it may be generated again later (deletion removes the suppression record).

---

## 5) Delete Confirmation and Responsive Layout

- [x] Deleting an applied item clearly warns that its active profile preference will also be removed.
- [x] Deleting a pending, rejected, or undone item clearly warns that the suggestion record will be permanently removed.
- [x] Cancel each delete confirmation; verify no data changes.
- [x] Confirm controls are usable without horizontal overflow at phone (`375x667`), tablet (`768x1024`), and desktop (`1366x768`) widths.
- [x] Verify keyboard focus order and visible focus states across edit fields and action buttons.

---

## 6) Bulk Selection and Actions

- [x] Select multiple pending rows individually and accept them; verify only selected rows move to Applied and all selected profile preferences are updated.
- [x] Use **Select all shown** in Pending, then reject; verify every displayed pending suggestion is rejected and none are applied to the profile.
- [x] Select multiple Applied rows and reject them; verify their preferences are removed from the profile and their records move to Rejected.
- [x] Select multiple Rejected rows and accept them; verify they move to Applied and update Likes/Dislikes.
- [x] Reopen selected Rejected/Undone rows; verify they return to Pending without changing the profile.
- [x] Bulk-delete selected rows from every section; verify selected records are permanently removed and unselected records remain.
- [x] Cancel bulk delete or bulk reject confirmation; verify no selected records or profile preferences change.
- [x] Submit a bulk action with no selected rows; verify a helpful warning and no data change.
- [x] Confirm bulk action totals report updated, deleted, and skipped items accurately.

---

## 7) Automated Regression Checks

Run:

```bash
.venv/bin/python -m unittest tests.test_profile_refinement_service -v
.venv/bin/python -m unittest tests.test_web_routes -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall app tests run.py
.venv/bin/python -m black --check app tests
.venv/bin/python -m flake8 app tests
```

- [x] Profile refinement service tests pass.
- [x] Web route tests pass.
- [x] Full test suite passes.
- [x] Compile, formatting, and lint checks pass.

---

## 7) Sign-off

Overall Result:
- [x] PASS
- [ ] FAIL - remediation required

Notes / Issues Found:

```
Nil
```

Sign-off:
- Name: Hutch
- Date: 26-10-10
