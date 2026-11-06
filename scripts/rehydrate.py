#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""SessionStart Rehydration Hook (`scripts/rehydrate.py`).

Scans `<workspace>/.scratch/*/index.md` for an active OKF v0.2 bundle and outputs
`{"injectSteps": [{"role": "system", "content": "..."}]}` on stdout so a fresh
conversation session automatically resumes with current stage and bundle context.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    yaml = None


def parse_frontmatter(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx == -1:
        return {}
    raw = "\n".join(lines[1:end_idx])
    if yaml is not None:
        try:
            parsed = yaml.safe_load(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    data: Dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip("'\"")
    return data


def find_active_bundles(workspace_dirs: List[Path]) -> List[Dict[str, Any]]:
    bundles: List[Dict[str, Any]] = []
    seen: set[Path] = set()
    for ws in workspace_dirs:
        scratch_dir = ws / ".scratch"
        if not scratch_dir.is_dir():
            continue
        for index_path in sorted(scratch_dir.glob("*/index.md")):
            resolved = index_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                content = index_path.read_text(encoding="utf-8")
            except Exception:
                continue
            fm = parse_frontmatter(content)
            bundle_dir = index_path.parent
            artifacts = sorted(
                p.name for p in bundle_dir.glob("*.md") if p.name not in ("index.md", "log.md")
            )
            bundles.append(
                {
                    "id": fm.get("id") or bundle_dir.name,
                    "name": fm.get("name") or bundle_dir.name,
                    "description": fm.get("description") or "",
                    "stage": fm.get("stage") or "0_triage",
                    "status": fm.get("status") or "active",
                    "bundle_path": str(bundle_dir),
                    "index_path": str(index_path),
                    "artifacts": artifacts,
                    "stages_completed": fm.get("stages_completed") or {},
                }
            )
    return bundles


def rehydrate_workspace(workspace_dirs: List[Path]) -> Dict[str, Any]:
    bundles = find_active_bundles(workspace_dirs)
    if not bundles:
        return {}

    lines = ["[Bean-Core Session Rehydration] Active OKF v0.2 bundle(s) detected in .scratch/:"]
    for b in bundles:
        artifacts_str = ", ".join(b["artifacts"]) if b["artifacts"] else "none yet"
        lines.append(
            f"- Bundle `{b['id']}` ({b['name']}) at `{b['bundle_path']}` | "
            f"stage: `{b['stage']}` | artifacts: [{artifacts_str}]"
        )
        if b["description"]:
            lines.append(f"  description: {b['description']}")
    lines.append("Read the bundle's `index.md` and `log.md` to resume workflow execution seamlessly.")
    msg = "\n".join(lines)
    return {
        "injectSteps": [
            {
                "role": "system",
                "content": msg,
                "systemMessage": {"systemMessage": msg},
            }
        ]
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SessionStart OKF bundle rehydration hook.")
    parser.add_argument("--workspace", action="append", dest="workspaces", help="Workspace directory path")
    args = parser.parse_args(argv)

    workspace_paths: List[Path] = []
    if args.workspaces:
        workspace_paths.extend(Path(p) for p in args.workspaces)

    if not sys.stdin.isatty():
        try:
            raw_stdin = sys.stdin.read().strip()
            if raw_stdin:
                payload = json.loads(raw_stdin)
                if isinstance(payload, dict):
                    for p in payload.get("workspacePaths", []):
                        workspace_paths.append(Path(p))
                    if payload.get("workspacePath"):
                        workspace_paths.append(Path(payload["workspacePath"]))
                    if payload.get("cwd"):
                        workspace_paths.append(Path(payload["cwd"]))
        except Exception:
            pass

    if not workspace_paths:
        workspace_paths.append(Path.cwd())

    result = rehydrate_workspace(workspace_paths)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
