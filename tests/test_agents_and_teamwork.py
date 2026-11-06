#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""Unit tests for subagent frontmatter normalization and Enterprise /teamwork governance."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import okf  # noqa: E402


class TestSubagentFrontmatterAndReferences(unittest.TestCase):
    """Covers AC1: review-arbiter.md & threat-modeler.md frontmatter normalization & dangling refs."""

    def test_subagent_frontmatter_normalized(self) -> None:
        for agent_name in ("review-arbiter", "threat-modeler"):
            agent_path = REPO_ROOT / "agents" / f"{agent_name}.md"
            self.assertTrue(agent_path.is_file(), f"Missing {agent_path}")
            fm, _, errs = okf.extract_frontmatter(agent_path)
            self.assertEqual(errs, [], f"Frontmatter errors in {agent_path}: {errs}")
            self.assertEqual(fm.get("kind"), "local", f"{agent_name} kind != local")
            self.assertIs(fm.get("subagent"), True, f"{agent_name} subagent != True")
            self.assertIs(fm.get("mainAgent"), False, f"{agent_name} mainAgent != False")
            self.assertEqual(fm.get("model"), "inherit", f"{agent_name} model != inherit")
            tools = fm.get("tools", [])
            self.assertEqual(tools, ["read_file", "run_command"], f"{agent_name} tools not normalized: {tools}")
            self.assertNotIn("grep_search", tools)
            self.assertNotIn("list_directory", tools)

    def test_review_arbiter_no_dangling_references(self) -> None:
        arbiter_text = (REPO_ROOT / "agents" / "review-arbiter.md").read_text(encoding="utf-8")
        self.assertNotIn("@architect", arbiter_text, "Dangling @architect reference found in review-arbiter.md")
        self.assertNotIn("@auditor", arbiter_text, "Dangling @auditor reference found in review-arbiter.md")
        self.assertIn("@system-design", arbiter_text)
        self.assertIn("@code-inspection", arbiter_text)


class TestStagesYamlTeamworkAndSubagents(unittest.TestCase):
    """Covers AC2: stages.yaml subagent registry & Enterprise /teamwork metadata."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = yaml.safe_load((REPO_ROOT / "stages.yaml").read_text(encoding="utf-8"))
        cls.stages = cls.registry["stages"]

    def test_heavy_authoring_subagents_registered(self) -> None:
        self.assertEqual(self.stages["0_ideation"].get("subagents"), ["product-ideator"])
        self.assertEqual(self.stages["1_questions"].get("subagents"), ["question-formulator"])
        self.assertIn("extraction-synthesizer", self.stages["2_blind_research"].get("subagents", []))
        self.assertIn("prd-author", self.stages["3_grill_and_prd"].get("subagents", []))
        self.assertIn("system-design", self.stages["4_spec"].get("subagents", []))
        self.assertEqual(self.stages["5_plan"].get("subagents"), ["system-design"])
        self.assertIn("walkthrough-recorder", self.stages["8_verify"].get("subagents", []))

    def test_enterprise_teamwork_metadata_in_council_and_tdd(self) -> None:
        council = self.stages["6a_council"]
        self.assertIs(council.get("enterprise_teamwork"), True)
        self.assertEqual(council.get("teamwork_trigger"), "carafe")
        modes = council.get("execution_modes", {})
        self.assertIn("cortado", modes)
        self.assertIn("carafe", modes)
        self.assertIn("invoke_subagent", modes["cortado"])
        self.assertIn("/teamwork", modes["carafe"])

        tdd = self.stages["7_tdd"]
        self.assertIs(tdd.get("enterprise_teamwork"), True)
        tdd_modes = tdd.get("execution_modes", {})
        self.assertIn("carafe", tdd_modes)
        self.assertIn("/teamwork", tdd_modes["carafe"])


class TestExpoAndRulesTeamworkGovernance(unittest.TestCase):
    """Covers AC3: agents/expo.md & rules/AGENTS.md Smart Zone delegation and /teamwork rules."""

    def test_expo_documents_authoring_delegation_and_teamwork(self) -> None:
        expo_text = (REPO_ROOT / "agents" / "expo.md").read_text(encoding="utf-8")
        for subagent in (
            "@product-ideator",
            "@question-formulator",
            "@extraction-synthesizer",
            "@prd-author",
            "@system-design",
            "@walkthrough-recorder",
        ):
            self.assertIn(subagent, expo_text, f"Missing {subagent} in agents/expo.md")
        self.assertIn("/teamwork", expo_text)
        self.assertIn("2_blind_research", expo_text)

    def test_rules_agents_md_documents_delegation_and_teamwork(self) -> None:
        rules_text = (REPO_ROOT / "rules" / "AGENTS.md").read_text(encoding="utf-8")
        for subagent in (
            "@product-ideator",
            "@question-formulator",
            "@extraction-synthesizer",
            "@prd-author",
            "@system-design",
            "@walkthrough-recorder",
        ):
            self.assertIn(subagent, rules_text, f"Missing {subagent} in rules/AGENTS.md")
        self.assertIn("/teamwork", rules_text)
        self.assertIn("2_blind_research", rules_text)


if __name__ == "__main__":
    unittest.main()
