#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""Comprehensive Unit Test Suite for Bean-Core & OKF v0.2 Engine (`tests/test_okf.py`).

Tests:
1. `okf.py`:
   - `init-bundle` (`index.md` with `type: bundle`, `okf_version: "0.2"`, and `log.md`).
   - `stamp` (`id` == stem, `generated`, `verified`, `sources` sha256/mtime, `stages_completed` pairs, and `log.md` entries).
   - `validate` (specifically proving that an invalid root-level markdown file in a bundle FAILS validation, confirming the root-file skip bug `rel_root == Path(".")` is fixed).
2. `rehydrate.py`: SessionStart hook output (`injectSteps`) when `.scratch/*/index.md` exists vs empty.
3. `git_guardrails.py`: PreToolUse hook denying `git push --force`, `git reset --hard`, `git clean -f`, and `git branch -D main|master`, while allowing `--force-with-lease` and safe commands.
4. `retro.py`: Backflush transcript miner counting steps, tool calls, `ERROR` steps, consecutive 3+ retry streaks, bytes/tokens, Smart Zone compliance (<100K tokens), and writing an OKF-stamped `08_RETRO.md`.
5. Schema validation of `scratch/bean-core/` (`plugin.json`, `stages.yaml`, `hooks.json`, `agents/*.md`, `skills/*/SKILL.md`, `rules/AGENTS.md`).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
PARENT_BEAN_CORE_DIR = Path("/home/robedwards/.gemini/antigravity/brain/b378ef20-777a-4118-8769-a131f94ede8a/scratch/bean-core")
LOCAL_BEAN_CORE_DIR = Path("/home/robedwards/.gemini/antigravity/brain/d59a964f-e729-4b33-a899-b2d5b5adaea6/scratch/bean-core")
BEAN_CORE_DIR = PARENT_BEAN_CORE_DIR if PARENT_BEAN_CORE_DIR.is_dir() else LOCAL_BEAN_CORE_DIR

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import git_guardrails  # noqa: E402
import okf  # noqa: E402
import rehydrate  # noqa: E402
import retro  # noqa: E402


class TestOKFEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.bundle_dir = Path(self.tmp.name) / "feat-espresso"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_bundle_creates_valid_index_and_log(self) -> None:
        rc = okf.main(["init-bundle", str(self.bundle_dir), "--id", "feat-espresso", "--description", "Espresso test bundle"])
        self.assertEqual(rc, 0)

        index_path = self.bundle_dir / "index.md"
        log_path = self.bundle_dir / "log.md"
        self.assertTrue(index_path.is_file())
        self.assertTrue(log_path.is_file())

        fm, _, errs = okf.extract_frontmatter(index_path)
        self.assertEqual(errs, [])
        self.assertEqual(fm.get("id"), "feat-espresso")
        self.assertEqual(fm.get("type"), "bundle")
        self.assertEqual(fm.get("okf_version"), "0.2")
        self.assertIn("Initialized OKF v0.2 bundle", log_path.read_text(encoding="utf-8"))

        res = okf.validate_bundle(self.bundle_dir)
        self.assertEqual(res.errors, [])

    def test_stamp_enforces_stem_id_hashes_sources_and_updates_log(self) -> None:
        okf.init_bundle(self.bundle_dir, bundle_id="feat-espresso")

        prd_path = self.bundle_dir / "03_PRD.md"
        prd_path.write_text("---\nid: wrong-id\ntype: prd\n---\n# PRD Body\n", encoding="utf-8")
        okf.stamp_file(
            file_path=prd_path,
            okf_type="prd",
            stage="3_grill_and_prd",
            by="bean-roaster/write-prd",
            status="stable",
            bundle_dir=self.bundle_dir,
        )
        expected_sha = hashlib.sha256(prd_path.read_bytes()).hexdigest()

        spec_path = self.bundle_dir / "04_SPEC.md"
        rc = okf.main(
            [
                "stamp",
                str(spec_path),
                "--type",
                "specification",
                "--stage",
                "4_spec",
                "--by",
                "bean-brewer/to-spec",
                "--name",
                "Technical Specification",
                "--status",
                "stable",
                "--source",
                "03_PRD.md",
                "--stage-pair",
                "cup_size=cortado",
                "--verified-by",
                "bean-core/threat-modeler",
                "--bundle-dir",
                str(self.bundle_dir),
            ]
        )
        self.assertEqual(rc, 0)

        fm, _, errs = okf.extract_frontmatter(spec_path)
        self.assertEqual(errs, [])
        self.assertEqual(fm["id"], "04_SPEC")
        self.assertEqual(fm["type"], "specification")
        self.assertEqual(fm["stage"], "4_spec")
        self.assertEqual(fm["status"], "stable")
        self.assertEqual(fm["generated"]["by"], "bean-brewer/to-spec")
        self.assertIn("at", fm["generated"])
        self.assertEqual(fm["verified"][0]["by"], "bean-core/threat-modeler")

        self.assertEqual(len(fm["sources"]), 1)
        src_entry = fm["sources"][0]
        self.assertEqual(src_entry["id"], "03_PRD")
        self.assertEqual(src_entry["resource"], "03_PRD.md")
        self.assertEqual(src_entry["sha256"], expected_sha)
        self.assertIn("last_modified", src_entry)

        self.assertEqual(fm["stages_completed"]["cup_size"], "cortado")
        self.assertIn("4_spec", fm["stages_completed"])

        log_text = (self.bundle_dir / "log.md").read_text(encoding="utf-8")
        self.assertIn("04_SPEC.md", log_text)
        self.assertIn("bean-brewer/to-spec", log_text)

        res = okf.validate_bundle(self.bundle_dir, require_stages_completed=True)
        self.assertEqual(res.errors, [])

    def test_validate_bundle_catches_invalid_root_level_file_bug_fixed(self) -> None:
        """Specifically verify that an invalid root-level .md file in a bundle FAILS validation."""
        okf.init_bundle(self.bundle_dir, bundle_id="feat-espresso")

        # Write a root-level markdown file with mismatched id and missing type
        bad_root_file = self.bundle_dir / "04_SPEC.md"
        bad_root_file.write_text(
            "---\nid: mismatched_id\n---\n# Invalid Root Entity\n",
            encoding="utf-8",
        )

        res = okf.validate_bundle(self.bundle_dir)
        self.assertGreater(len(res.errors), 0, "Expected root-level invalid markdown file to fail validation")
        combined_errors = "\n".join(res.errors)
        self.assertIn("04_SPEC.md", combined_errors)
        self.assertIn("Mismatched 'id'", combined_errors)
        self.assertIn("Missing required 'type'", combined_errors)

        # Also verify CLI returns non-zero exit code
        cli_rc = okf.main(["validate", str(self.bundle_dir)])
        self.assertEqual(cli_rc, 1)


class TestRehydrateHook(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_rehydrate_empty_workspace(self) -> None:
        out = rehydrate.rehydrate_workspace([self.ws])
        self.assertEqual(out, {})

    def test_rehydrate_active_scratch_bundle(self) -> None:
        bundle_dir = self.ws / ".scratch" / "order-42"
        okf.init_bundle(bundle_dir, bundle_id="order-42", description="OAuth2 PKCE flow")
        spec = bundle_dir / "04_SPEC.md"
        okf.stamp_file(spec, okf_type="specification", stage="4_spec", by="bean-brewer/to-spec", bundle_dir=bundle_dir)

        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "rehydrate.py")],
            input=json.dumps({"workspacePaths": [str(self.ws)]}),
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        self.assertIn("injectSteps", data)
        self.assertEqual(len(data["injectSteps"]), 1)
        step = data["injectSteps"][0]
        self.assertEqual(step["role"], "system")
        self.assertIn("order-42", step["content"])
        self.assertIn("04_SPEC.md", step["content"])


class TestGitGuardrailsHook(unittest.TestCase):
    def _run_hook(self, payload: dict) -> dict:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "git_guardrails.py")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)

    def test_denies_destructive_git_commands(self) -> None:
        destructive_cmds = [
            "git push --force origin main",
            "git push -f origin feat/test",
            "git reset --hard HEAD~1",
            "git clean -f",
            "git clean -fd",
            "git branch -D main",
            "git branch -D master",
        ]
        for cmd in destructive_cmds:
            with self.subTest(cmd=cmd):
                res = self._run_hook({"tool_input": {"CommandLine": cmd}})
                self.assertEqual(res["decision"], "deny")
                self.assertTrue(res.get("reason"))

    def test_allows_safe_and_force_with_lease_commands(self) -> None:
        safe_cmds = [
            "git status",
            "git push --force-with-lease origin feat/test",
            "git push origin feat/test",
            "git reset --soft HEAD~1",
            "git clean -n",
            "git branch -D feat/old-branch",
            "python3 -m unittest",
        ]
        for cmd in safe_cmds:
            with self.subTest(cmd=cmd):
                res = self._run_hook({"toolCall": {"name": "run_command", "args": {"CommandLine": cmd}}})
                self.assertEqual(res["decision"], "allow")


class TestRetroMiner(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_retro_mines_transcript_and_stamps_okf_report(self) -> None:
        transcript_path = self.base / "transcript.jsonl"
        bundle_dir = self.base / "plan-bundle"

        steps = [
            {"step_index": 0, "status": "DONE", "tool_calls": [{"name": "read_file"}]},
            {"step_index": 1, "status": "ERROR", "tool_calls": [{"name": "run_command"}]},
            {"step_index": 2, "status": "ERROR", "tool_calls": [{"name": "run_command"}]},
            {"step_index": 3, "status": "DONE", "tool_calls": [{"name": "run_command"}]},
            {"step_index": 4, "status": "DONE", "tool_calls": [{"name": "edit_file"}]},
        ]
        transcript_path.write_text("\n".join(json.dumps(s) for s in steps) + "\n", encoding="utf-8")

        metrics = retro.write_retro_report(transcript_path, bundle_dir)
        self.assertEqual(metrics["total_steps"], 5)
        self.assertEqual(metrics["total_tool_calls"], 5)
        self.assertEqual(metrics["error_steps"], 2)
        self.assertEqual(len(metrics["retry_streaks"]), 1)
        self.assertEqual(metrics["retry_streaks"][0], {"tool": "run_command", "count": 3})
        self.assertTrue(metrics["smart_zone_compliant"])

        retro_file = bundle_dir / "08_RETRO.md"
        self.assertTrue(retro_file.is_file())
        fm, _, errs = okf.extract_frontmatter(retro_file)
        self.assertEqual(errs, [])
        self.assertEqual(fm["id"], "08_RETRO")
        self.assertEqual(fm["type"], "retrospective")
        self.assertEqual(fm["stage"], "9_retro")
        self.assertEqual(fm["stages_completed"]["retry_streaks"], "1")

        val = okf.validate_bundle(bundle_dir, require_stages_completed=True)
        self.assertEqual(val.errors, [])


class TestBeanCorePluginSchema(unittest.TestCase):
    def test_bean_core_files_and_schemas(self) -> None:
        self.assertTrue(BEAN_CORE_DIR.is_dir(), f"Missing {BEAN_CORE_DIR}")

        # 1. plugin.json
        plugin_json = BEAN_CORE_DIR / "plugin.json"
        self.assertTrue(plugin_json.is_file())
        plugin_data = json.loads(plugin_json.read_text(encoding="utf-8"))
        self.assertEqual(plugin_data.get("name"), "bean-core")

        # 2. stages.yaml
        stages_yaml = BEAN_CORE_DIR / "stages.yaml"
        self.assertTrue(stages_yaml.is_file())
        stages_data = yaml.safe_load(stages_yaml.read_text(encoding="utf-8"))
        self.assertEqual(stages_data.get("okf_version"), "0.2")
        for cs in ("ristretto", "cortado", "carafe"):
            self.assertIn(cs, stages_data.get("cup_sizes", {}))
        for orig in ("greenfield", "brownfield", "legacy"):
            self.assertIn(orig, stages_data.get("origins", {}))
        self.assertIn("0_triage", stages_data.get("stages", {}))
        self.assertIn("9_retro", stages_data.get("stages", {}))

        # 3. hooks.json
        hooks_json = BEAN_CORE_DIR / "hooks.json"
        self.assertTrue(hooks_json.is_file())
        hooks_data = json.loads(hooks_json.read_text(encoding="utf-8"))
        self.assertIn("bean-core", hooks_data)
        bc_hooks = hooks_data["bean-core"]

        # SessionStart flat array
        session_start = bc_hooks.get("SessionStart")
        self.assertIsInstance(session_start, list)
        self.assertGreater(len(session_start), 0)
        for h in session_start:
            self.assertIn("command", h)
            self.assertNotIn("hooks", h)
            self.assertLessEqual(h.get("timeout", 30), 30)

        # PreToolUse with matcher: "run_command"
        pre_tool = bc_hooks.get("PreToolUse")
        self.assertIsInstance(pre_tool, list)
        self.assertEqual(pre_tool[0].get("matcher"), "run_command")
        for h in pre_tool[0].get("hooks", []):
            self.assertLessEqual(h.get("timeout", 30), 30)

        # PostToolUse with matcher: "write_file|edit_file|replace_file_content|write_to_file"
        post_tool = bc_hooks.get("PostToolUse")
        self.assertIsInstance(post_tool, list)
        self.assertEqual(
            post_tool[0].get("matcher"),
            "write_file|edit_file|replace_file_content|write_to_file",
        )
        for h in post_tool[0].get("hooks", []):
            self.assertLessEqual(h.get("timeout", 30), 30)

        # 4. agents/*.md
        for agent_name in ("expo", "review-arbiter", "threat-modeler"):
            agent_path = BEAN_CORE_DIR / "agents" / f"{agent_name}.md"
            self.assertTrue(agent_path.is_file(), f"Missing {agent_path}")
            fm, _, errs = okf.extract_frontmatter(agent_path)
            self.assertEqual(errs, [], f"Frontmatter errors in {agent_path}: {errs}")
            self.assertEqual(fm.get("name"), agent_name)
            self.assertTrue(fm.get("description"))

        # 5. skills/*/SKILL.md
        for skill_name in ("triage", "retro"):
            skill_path = BEAN_CORE_DIR / "skills" / skill_name / "SKILL.md"
            self.assertTrue(skill_path.is_file(), f"Missing {skill_path}")
            fm, _, errs = okf.extract_frontmatter(skill_path)
            self.assertEqual(errs, [], f"Frontmatter errors in {skill_path}: {errs}")
            self.assertEqual(fm.get("name"), skill_name)
            self.assertTrue(fm.get("description"))

        # 6. rules/AGENTS.md (plain markdown, no YAML frontmatter)
        agents_rule = BEAN_CORE_DIR / "rules" / "AGENTS.md"
        self.assertTrue(agents_rule.is_file())
        rule_text = agents_rule.read_text(encoding="utf-8")
        self.assertFalse(rule_text.lstrip().startswith("---"), "rules/AGENTS.md must not have YAML frontmatter")

        # 7. Required scripts present in scratch/bean-core/scripts/
        for script_name in (
            "validate_okf.py",
            "okf_stamp.py",
            "okf.py",
            "rehydrate.py",
            "git_guardrails.py",
            "retro.py",
        ):
            self.assertTrue((BEAN_CORE_DIR / "scripts" / script_name).is_file(), f"Missing {script_name}")


if __name__ == "__main__":
    unittest.main()
