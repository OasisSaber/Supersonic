"""Unit tests for the standard-library Markdown local-link validator."""

import tempfile
import unittest
from pathlib import Path

from validate_markdown_links import markdown_targets, strip_ignored_regions, validate_paths


class MarkdownLinkTests(unittest.TestCase):
    def validate(self, text, files=()):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "guide.md"
            source.parent.mkdir()
            source.write_text(text, encoding="utf-8")
            for name in files:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok", encoding="utf-8")
            return validate_paths(root, [source])

    def test_inline_image_parentheses_encoded_and_query_targets(self):
        text = "[doc](example(1).md) ![img](../assets/image.png) [space](example%20file.md?view=1#part)"
        self.assertEqual([], self.validate(text, ["docs/example(1).md", "assets/image.png", "docs/example file.md"]))

    def test_reference_and_html_targets(self):
        text = '[ref][guide] <a href="../index.md">x</a><img src="../assets/image.png">\n[guide]: target.md'
        self.assertEqual([], self.validate(text, ["docs/target.md", "index.md", "assets/image.png"]))

    def test_external_anchor_code_and_comment_are_skipped(self):
        text = "[web](https://example.com) [mail](mailto:a@b.test) [anchor](#a) [proto](//example.com) `[](missing.md)` <!-- [x](missing.md) -->\n    [x](missing.md)\n```md\n[x](missing.md)\n```"
        self.assertEqual([], self.validate(text))

    def test_missing_reference_and_missing_target_fail(self):
        self.assertTrue(self.validate("[missing][nope]"))
        self.assertTrue(self.validate("[missing](nope.md)"))

    def test_escape_and_root_relative_paths(self):
        self.assertTrue(self.validate("[escape](../../outside.md)"))
        self.assertEqual([], self.validate("[root](/root.md)", ["root.md"]))

    def test_parser_self_check_for_nested_link(self):
        targets = markdown_targets(strip_ignored_regions("[nested](docs/example(1).md)"))
        self.assertEqual(["docs/example(1).md"], targets)


if __name__ == "__main__":
    unittest.main()
