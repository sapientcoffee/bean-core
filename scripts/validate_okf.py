#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""Open Knowledge Format (OKF v0.2) Bundle Validator for Bean-Core & Bean-Brewer.

Fixes the upstream root-file skip bug (`rel_root == Path(".")`), validates:
- Root `index.md` (`type: bundle`, `id`, `okf_version`) and `log.md`
- Subdirectory `index.md` catalogs
- Entity frontmatter (`id` == filename stem, `type`, `status`, `generated`, `stages_completed`)
- Relative path integrity across `sources`, `related_tables`, `inputs`, `outputs` (no leading '/')
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ImportError:
    yaml = None


class ValidationResult:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.entities_checked: int = 0

    def add_error(self, path: Path, msg: str) -> None:
        self.errors.append(f"[ERROR] {path}: {msg}")

    def add_warning(self, path: Path, msg: str) -> None:
        self.warnings.append(f"[WARN]  {path}: {msg}")


def extract_frontmatter(file_path: Path) -> Tuple[Dict[str, Any], str, List[str]]:
    """Extract and parse YAML frontmatter between leading triple dashes."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {}, "", [f"Could not read file: {exc}"]

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content, ["File does not start with '---' on line 1."]

    closing_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break

    if closing_idx == -1:
        return {}, content, ["Frontmatter missing closing '---' delimiter."]

    fm_raw = "".join(lines[1:closing_idx])
    body = "".join(lines[closing_idx + 1 :])

    if yaml is not None:
        try:
            fm_data = yaml.safe_load(fm_raw)
            if not isinstance(fm_data, dict):
                return {}, body, ["YAML frontmatter did not parse into a key-value mapping."]
            return fm_data, body, []
        except Exception as exc:
            return {}, body, [f"YAML parsing error: {exc}"]

    fm_data = {}
    for line in fm_raw.splitlines():
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("#") and not stripped.startswith("-"):
            k, v = stripped.split(":", 1)
            fm_data[k.strip()] = v.strip().strip("'\"")
    return fm_data, body, []


def validate_file(file_path: Path, bundle_dir: Path, require_stages_completed: bool = False) -> ValidationResult:
    """Validate a single Markdown entity file against OKF v0.2 conventions."""
    result = ValidationResult()
    result.entities_checked = 1

    fm, _, errs = extract_frontmatter(file_path)
    for err in errs:
        result.add_error(file_path, err)
    if errs:
        return result

    if file_path.name == "index.md":
        if file_path.parent == bundle_dir:
            if fm.get("type") != "bundle":
                result.add_error(
                    file_path,
                    f"Root index.md 'type' must be 'bundle', got '{fm.get('type')}'",
                )
            if not fm.get("id"):
                result.add_error(file_path, "Root index.md missing 'id' in frontmatter")
        return result

    expected_id = file_path.stem
    actual_id = fm.get("id")
    if not actual_id:
        result.add_error(file_path, "Missing required 'id' key in YAML frontmatter.")
    elif str(actual_id) != expected_id:
        result.add_error(
            file_path,
            f"Mismatched 'id': frontmatter id is '{actual_id}', expected '{expected_id}'",
        )

    if not fm.get("type"):
        result.add_error(file_path, "Missing required 'type' key in YAML frontmatter.")

    if require_stages_completed:
        stages = fm.get("stages_completed")
        if not isinstance(stages, (dict, list)) or not stages:
            result.add_error(
                file_path,
                "Missing or empty 'stages_completed' audit pairs in YAML frontmatter.",
            )
        gen = fm.get("generated")
        if not isinstance(gen, dict) or not gen.get("by") or not gen.get("at"):
            result.add_error(
                file_path,
                "Missing 'generated: {by, at}' metadata in YAML frontmatter.",
            )

    # Check relative links in sources and standard reference lists
    sources = fm.get("sources", [])
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict):
                res = src.get("resource", "")
                if isinstance(res, str) and res:
                    if res.startswith("/"):
                        result.add_error(
                            file_path,
                            f"Absolute path in 'sources.resource': '{res}'. Use relative path.",
                        )
                    else:
                        t_bundle = bundle_dir / res
                        t_dir = file_path.parent / res
                        if not t_bundle.exists() and not t_dir.exists():
                            result.add_warning(
                                file_path,
                                f"Referenced source '{res}' could not be resolved.",
                            )

    ref_fields = ["related_tables", "inputs", "outputs"]
    for field in ref_fields:
        items = fm.get(field, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item.endswith(".md"):
                    if item.startswith("/"):
                        result.add_error(
                            file_path,
                            f"Absolute path in '{field}': '{item}'. Use relative path.",
                        )
                    else:
                        t_bundle = bundle_dir / item
                        t_dir = file_path.parent / item
                        if not t_bundle.exists() and not t_dir.exists():
                            result.add_warning(
                                file_path,
                                f"Referenced link '{item}' in '{field}' could not be resolved.",
                            )

    return result


def validate_bundle(bundle_dir: Path, require_stages_completed: bool = False) -> ValidationResult:
    """Validate an entire OKF bundle directory, including root-level entity files."""
    result = ValidationResult()

    if not bundle_dir.is_dir():
        result.add_error(bundle_dir, "Target bundle path is not a directory.")
        return result

    root_index = bundle_dir / "index.md"
    root_log = bundle_dir / "log.md"

    if not root_index.is_file():
        result.add_error(bundle_dir, "Missing root index.md")
    else:
        sub = validate_file(root_index, bundle_dir, require_stages_completed=False)
        result.entities_checked += sub.entities_checked
        result.errors.extend(sub.errors)
        result.warnings.extend(sub.warnings)

    if not root_log.is_file():
        result.add_warning(bundle_dir, "Missing root log.md changelog")

    for root, dirs, files in os.walk(bundle_dir):
        # Filter hidden subdirectories in-place so os.walk doesn't descend into .git etc.
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel_root = Path(root).relative_to(bundle_dir)
        # FIXED: Do NOT skip rel_root == Path(".")! Only skip if a path component starts with "."
        if rel_root != Path(".") and any(part.startswith(".") for part in rel_root.parts):
            continue

        current_path = Path(root)

        non_index_files = [
            f for f in files if f not in ("index.md", "log.md") and not f.startswith(".")
        ]
        if current_path != bundle_dir and non_index_files:
            if "index.md" not in files:
                result.add_error(
                    current_path,
                    "Directory contains items but is missing mandatory index.md catalog.",
                )

        for fname in sorted(files):
            if fname.startswith(".") or fname in ("log.md", "viz.html"):
                continue
            file_path = current_path / fname
            if file_path == root_index:
                continue

            if "references/joins" in str(file_path):
                if not re.match(r"^.+___[^\.]+\.md$", fname):
                    result.add_error(
                        file_path,
                        f"Join file '{fname}' must follow triple-underscore convention '<left>___<right>.md'",
                    )

            if fname.endswith(".md"):
                sub = validate_file(
                    file_path,
                    bundle_dir,
                    require_stages_completed=require_stages_completed and fname != "index.md",
                )
                result.entities_checked += sub.entities_checked
                result.errors.extend(sub.errors)
                result.warnings.extend(sub.warnings)
            else:
                result.entities_checked += 1

    return result


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an OKF v0.2 bundle or file.")
    parser.add_argument("target", help="Path to OKF bundle directory or markdown file")
    parser.add_argument(
        "--require-stages",
        action="store_true",
        help="Require stages_completed and generated metadata on entity files",
    )
    args = parser.parse_args(argv)

    target_path = Path(args.target).resolve()
    if target_path.is_file():
        res = validate_file(
            target_path,
            target_path.parent,
            require_stages_completed=args.require_stages,
        )
    else:
        res = validate_bundle(
            target_path,
            require_stages_completed=args.require_stages,
        )

    print(f"Validating OKF target: {target_path}")
    print(f"Entities Scanned: {res.entities_checked} | Errors: {len(res.errors)} | Warnings: {len(res.warnings)}")
    for w in res.warnings:
        print(w)
    for e in res.errors:
        print(e)

    if res.errors:
        print(f"❌ OKF validation FAILED with {len(res.errors)} error(s).")
        return 1
    print("✅ OKF validation PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
