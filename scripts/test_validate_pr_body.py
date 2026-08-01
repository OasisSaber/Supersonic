"""Tests for the pull-request-body validator.

Adapted from OasisSaber/AgenticWonderwall (MIT), commits
689d4edb8aacc1fc7a277da89efed05199b75edb and
794b083e816e84f271e991aed84a5a5f4e9c74fc. See THIRD_PARTY_NOTICES.md.
"""

import unittest

from validate_pr_body import REQUIRED_REVIEW_ITEMS, validate

REVIEW = "\n".join(f"- [x] {item}" for item in REQUIRED_REVIEW_ITEMS)
ISSUE_BASE = f"""## Related task
- Issue: Closes #4

## What changed / Result
Done.

## Why
Required workflow adoption.

## Screens / evidence
Not applicable: workflow-only change.

## Verification
Tests passed.

## Scope and risks
- Out of scope: product code.
- Known risks: none.
- Follow-up: human review.

## Agent self-review
{REVIEW}

## Notes for human
Ready for review.
"""

AUTHORIZATION_BASE = ISSUE_BASE.replace(
    "- Issue: Closes #4",
    "- Explicit human authorization:\n  - Authorization source: current chat\n  - Goal: workflow fix\n  - Scope: scripts",
)


class ValidatePrBodyTests(unittest.TestCase):
    def test_valid_issue_only(self):
        self.assertEqual([], validate(ISSUE_BASE))

    def test_all_supported_closing_keywords_are_valid(self):
        for reference in ("Close #4", "Closed #4", "Fix #4", "Fixes #4", "Fixed #4", "Resolve #4", "Resolves #4", "Resolved #4"):
            with self.subTest(reference=reference):
                self.assertEqual([], validate(ISSUE_BASE.replace("Closes #4", reference)))

    def test_valid_authorization_only(self):
        self.assertEqual([], validate(AUTHORIZATION_BASE))

    def test_issue_plus_empty_authorization_block_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("\n\n## What changed", "\n- Explicit human authorization:\n\n## What changed")))

    def test_authorization_plus_empty_issue_line_fails(self):
        self.assertTrue(validate(AUTHORIZATION_BASE.replace("\n\n## What changed", "\n- Issue:\n\n## What changed")))

    def test_both_complete_paths_fail(self):
        self.assertTrue(validate(ISSUE_BASE.replace("\n\n## What changed", "\n- Explicit human authorization:\n  - Authorization source: chat\n  - Goal: docs\n  - Scope: scripts\n\n## What changed")))

    def test_neither_path_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("- Issue: Closes #4\n", "")))

    def test_issue_placeholder_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("#4", "#<number>")))

    def test_placeholder_outside_task_source_is_allowed(self):
        self.assertEqual([], validate(ISSUE_BASE.replace("Done.", "Rendered label: <number>.")))

    def test_empty_issue_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("Closes #4", "")))

    def test_partial_authorization_fails(self):
        self.assertTrue(validate(AUTHORIZATION_BASE.replace("  - Scope: scripts\n", "")))

    def test_orphan_authorization_field_fails(self):
        self.assertTrue(validate(AUTHORIZATION_BASE.replace("- Explicit human authorization:\n", "")))

    def test_duplicate_issue_path_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("- Issue: Closes #4", "- Issue: Closes #4\n- Issue: Closes #5")))

    def test_bare_issue_reference_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("Closes #4", "#4")))

    def test_non_closing_issue_text_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("Closes #4", "Reviewed in #4")))

    def test_multiple_issue_references_fail(self):
        self.assertTrue(validate(ISSUE_BASE.replace("Closes #4", "Closes #4 and fixes #5")))

    def test_cross_repository_issue_reference_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("Closes #4", "Closes OasisSaber/AgenticWonderwall#4")))

    def test_dormant_authorization_path_in_html_comment_is_ignored(self):
        dormant = """<!--
- Explicit human authorization:
  - Authorization source: <source>
  - Goal: <goal>
  - Scope: <scope>
-->"""
        self.assertEqual([], validate(ISSUE_BASE.replace("\n\n## What changed", f"\n{dormant}\n\n## What changed")))

    def test_comment_only_issue_path_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("- Issue: Closes #4", "<!-- - Issue: Closes #4 -->")))

    def test_comment_only_required_section_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("Done.", "<!-- Done. -->")))

    def test_comment_only_checked_review_item_fails(self):
        item = REQUIRED_REVIEW_ITEMS[0]
        self.assertTrue(validate(ISSUE_BASE.replace(f"- [x] {item}", f"<!-- - [x] {item} -->")))

    def test_empty_required_section_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace("Done.", "")))

    def test_unchecked_review_item_fails(self):
        self.assertTrue(validate(ISSUE_BASE.replace(f"[x] {REQUIRED_REVIEW_ITEMS[0]}", f"[ ] {REQUIRED_REVIEW_ITEMS[0]}")))


if __name__ == "__main__":
    unittest.main()
