#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""Documentation drift tests (`tests/test_docs.py`).

Keeps `docs/index.html` (interactive architecture explorer) honest:
1. Every stage in `stages.yaml` appears in the page's STAGES data with the same plugin,
   artifact, okf_type and `next` list; cup-size stage lists and gates match.
2. Every `{fn, file, lines}` function reference points at the real `def <fn>` line, so
   "view source" links never drift when scripts change.
3. Every script in `scripts/` is mentioned in the page.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_HTML = REPO_ROOT / "docs" / "index.html"
STAGES_YAML = REPO_ROOT / "stages.yaml"

FN_REF = re.compile(r"\{\s*fn:\s*\"(\w+)\",\s*file:\s*\"([^\"]+)\",\s*lines:\s*\[(\d+),\s*(\d+)\]")


def _js_object_literal(html: str, const_name: str) -> str:
    """Return the `{...}` literal assigned to `const <name> =` using brace matching."""
    start = html.index(f"const {const_name} = {{") + len(f"const {const_name} = ")
    depth = 0
    in_str = None
    for idx in range(start, len(html)):
        ch = html[idx]
        if in_str:
            if ch == "\\":
                continue
            if ch == in_str and html[idx - 1] != "\\":
                in_str = None
            continue
        if ch in "\"'`":
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return html[start : idx + 1]
    raise AssertionError(f"Unterminated object literal for {const_name}")


def _js_to_json(literal: str) -> object:
    """Convert a simple JS object literal (quoted string keys or bare identifiers) to Python."""
    text = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', literal)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


class TestInteractiveDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = DOCS_HTML.read_text(encoding="utf-8")
        cls.registry = yaml.safe_load(STAGES_YAML.read_text(encoding="utf-8"))

    def test_stage_data_matches_stages_yaml(self) -> None:
        stages = _js_to_json(_js_object_literal(self.html, "STAGES"))
        self.assertEqual(set(stages), set(self.registry["stages"]), "Stage keys differ from stages.yaml")
        for key, spec in self.registry["stages"].items():
            doc = stages[key]
            for field in ("coffee_name", "plugin", "skill", "artifact", "okf_type", "bundle", "next",
                          "subagents", "script", "followup_skill", "durable_outputs",
                          "workspace_mode", "max_parallel_workers", "walkthrough_artifact"):
                self.assertEqual(doc.get(field), spec.get(field), f"{key}.{field} drifted from stages.yaml")

    def test_cup_sizes_and_origins_match(self) -> None:
        cups = _js_to_json(_js_object_literal(self.html, "CUP_SIZES"))
        for name, spec in self.registry["cup_sizes"].items():
            self.assertEqual(cups[name]["stages"], spec["stages"], f"{name} stages drifted")
            self.assertEqual(cups[name]["gate"], spec["gate"], f"{name} gate drifted")
            self.assertEqual(cups[name]["description"], spec["description"], f"{name} description drifted")
        origins = _js_to_json(_js_object_literal(self.html, "ORIGINS"))
        self.assertEqual(origins, self.registry["origins"])

    def test_function_references_point_at_def_lines(self) -> None:
        refs = FN_REF.findall(self.html)
        self.assertGreaterEqual(len(refs), 15, "Expected function references in docs/index.html")
        for fn, rel, start, end in refs:
            path = REPO_ROOT / rel
            self.assertTrue(path.is_file(), f"Referenced file {rel} missing")
            lines = path.read_text(encoding="utf-8").splitlines()
            start_i, end_i = int(start), int(end)
            self.assertLessEqual(start_i, end_i, f"{fn}: inverted range")
            self.assertLessEqual(end_i, len(lines), f"{fn}: range past EOF in {rel}")
            self.assertRegex(lines[start_i - 1], rf"^\s*def {fn}\(", f"{rel}:{start_i} is not `def {fn}(`")

    def test_every_script_is_documented(self) -> None:
        for script in sorted((REPO_ROOT / "scripts").glob("*.py")):
            self.assertIn(script.name, self.html, f"scripts/{script.name} is not documented in docs/index.html")

    def test_demo_doc_exists_and_is_linked_from_readme(self) -> None:
        demo_path = REPO_ROOT / "demo.md"
        readme_path = REPO_ROOT / "README.md"
        self.assertTrue(demo_path.is_file(), "demo.md is missing from bean-core root")
        readme_text = readme_path.read_text(encoding="utf-8")
        self.assertIn("(demo.md)", readme_text, "README.md must link to demo.md")
        demo_text = demo_path.read_text(encoding="utf-8")
        self.assertIn("Antigravity 2.0", demo_text)
        self.assertIn("Antigravity CLI", demo_text)


if __name__ == "__main__":
    unittest.main()
