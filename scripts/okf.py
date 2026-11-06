#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""Unified OKF v0.2 Validation & Frontmatter Stamping Engine (`scripts/okf.py`).

Provides both programmatic and CLI interfaces for:
1. Initializing OKF v0.2 bundles (`init-bundle`) with `index.md` (`type: bundle`) and `log.md`.
2. Deterministically stamping OKF v0.2 frontmatter (`id` == stem, `type`, `name`, `description`,
   `status`, `stage`, `generated`, `verified`, `sources` with SHA-256 + mtime, and
   `stages_completed` key-value audit pairs) onto stage artifacts (`stamp`).
3. Validating OKF bundles and individual entity files (`validate`), fixing the upstream
   `rel_root == Path(".")` root-file skip bug.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
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


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def file_mtime_iso(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def render_markdown(frontmatter: Dict[str, Any], body: str) -> str:
    if yaml is not None:
        fm_str = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    else:
        fm_str = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    if body and not body.startswith("\n"):
        body = "\n" + body
    return f"---\n{fm_str}\n---\n{body}"


def append_log(bundle_dir: Path, stage: str, actor: str, artifact: str, note: str = "") -> None:
    log_path = bundle_dir / "log.md"
    now = utc_now_iso()
    if not log_path.exists():
        log_path.write_text("# OKF Bundle Changelog\n\n", encoding="utf-8")
    entry = f"## {now} — {stage}\n- **by:** `{actor}`\n- **artifact:** `{artifact}`\n"
    if note:
        entry += f"- **note:** {note}\n"
    entry += "\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)


def refresh_index(bundle_dir: Path, bundle_id: str | None = None, description: str | None = None) -> Path:
    index_path = bundle_dir / "index.md"
    now = utc_now_iso()
    if index_path.exists():
        fm, _, _ = extract_frontmatter(index_path)
    else:
        fm = {}

    b_id = bundle_id or fm.get("id") or bundle_dir.name
    fm["id"] = b_id
    fm["type"] = "bundle"
    fm["okf_version"] = "0.2"
    fm["name"] = fm.get("name") or f"OKF Bundle: {b_id}"
    fm["description"] = description or fm.get("description") or f"SDLC artifact bundle for {b_id}."
    fm["updated_at"] = now

    rows = []
    for p in sorted(bundle_dir.glob("*.md")):
        if p.name in ("index.md", "log.md"):
            continue
        pfm, _, _ = extract_frontmatter(p)
        ptype = pfm.get("type", "unknown")
        pstatus = pfm.get("status", "draft")
        pdesc = pfm.get("description") or pfm.get("name") or p.stem
        rows.append(f"| [{p.stem}]({p.name}) | `{ptype}` | `{pstatus}` | {pdesc} |")

    table = "\n".join(rows) if rows else "| *(empty)* | - | - | - |"
    body = (
        f"\n# {fm['name']}\n\n"
        f"{fm['description']}\n\n"
        "## Bundle Catalog\n\n"
        "| ID | Type | Status | Description |\n"
        "| :--- | :--- | :--- | :--- |\n"
        f"{table}\n"
    )
    index_path.write_text(render_markdown(fm, body), encoding="utf-8")
    return index_path


def init_bundle(bundle_dir: Path, bundle_id: str | None = None, description: str | None = None) -> int:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    refresh_index(bundle_dir, bundle_id=bundle_id, description=description)
    append_log(bundle_dir, "0_triage", "bean-core/okf", "index.md", "Initialized OKF v0.2 bundle")
    return 0


def stamp_file(
    file_path: Path,
    okf_type: str,
    stage: str,
    by: str,
    name: str | None = None,
    description: str | None = None,
    status: str = "draft",
    sources: List[str] | None = None,
    stage_pairs: Dict[str, str] | List[str] | None = None,
    verified_by: str | None = None,
    bundle_dir: Path | None = None,
) -> int:
    b_dir = bundle_dir or file_path.parent
    b_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now_iso()

    if file_path.exists():
        existing_fm, body, _ = extract_frontmatter(file_path)
    else:
        existing_fm, body = {}, f"\n# {name or file_path.stem}\n"

    fm: Dict[str, Any] = {}
    fm["id"] = file_path.stem
    fm["type"] = okf_type or existing_fm.get("type", "document")
    fm["name"] = name or existing_fm.get("name") or file_path.stem
    fm["description"] = description or existing_fm.get("description") or f"{fm['name']} ({stage})"
    fm["status"] = status or existing_fm.get("status", "draft")
    fm["stage"] = stage
    fm["generated"] = {"by": by, "at": now}

    verified_list = existing_fm.get("verified", [])
    if not isinstance(verified_list, list):
        verified_list = []
    if verified_by:
        verified_list.append({"by": verified_by, "at": now})
    if verified_list:
        fm["verified"] = verified_list

    source_entries = existing_fm.get("sources", [])
    if not isinstance(source_entries, list):
        source_entries = []
    if sources is not None:
        source_entries = []
        for src_rel in sources:
            src_clean = src_rel.lstrip("/")
            src_path = (file_path.parent / src_clean).resolve()
            if not src_path.exists():
                src_path = (b_dir / src_clean).resolve()
            entry: Dict[str, Any] = {
                "id": Path(src_clean).stem,
                "resource": src_clean,
            }
            if src_path.exists() and src_path.is_file():
                entry["last_modified"] = file_mtime_iso(src_path)
                entry["sha256"] = file_sha256(src_path)
            source_entries.append(entry)
    if source_entries:
        fm["sources"] = source_entries

    stages_map = existing_fm.get("stages_completed", {})
    if not isinstance(stages_map, dict):
        stages_map = {}
    if isinstance(stage_pairs, dict):
        stages_map.update(stage_pairs)
    elif isinstance(stage_pairs, list):
        for pair in stage_pairs:
            if "=" in pair:
                k, v = pair.split("=", 1)
                stages_map[k.strip()] = v.strip()
    stages_map[stage] = f"{by} ({now})"
    fm["stages_completed"] = stages_map

    reserved = {
        "id", "type", "name", "description", "status", "stage",
        "generated", "verified", "sources", "stages_completed",
    }
    for k, v in existing_fm.items():
        if k not in reserved:
            fm[k] = v

    file_path.write_text(render_markdown(fm, body), encoding="utf-8")
    if (b_dir / "index.md").exists():
        refresh_index(b_dir)
    if (b_dir / "log.md").exists():
        append_log(b_dir, stage, by, file_path.name, f"Stamped {file_path.name} [{fm['status']}]")
    return 0


def validate_file(
    file_path: Path,
    bundle_dir: Path,
    require_stages_completed: bool = False,
) -> ValidationResult:
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

    for field in ("related_tables", "inputs", "outputs"):
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


def validate_bundle(
    bundle_dir: Path,
    require_stages_completed: bool = False,
) -> ValidationResult:
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
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel_root = Path(root).relative_to(bundle_dir)
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
    parser = argparse.ArgumentParser(description="OKF v0.2 Validation & Frontmatter Engine")
    sub = parser.add_subparsers(dest="cmd")

    p_init = sub.add_parser("init-bundle", help="Initialize an OKF bundle root")
    p_init.add_argument("bundle_dir", help="Bundle directory path")
    p_init.add_argument("--id", dest="bundle_id", help="Bundle identifier")
    p_init.add_argument("--description", help="Bundle description")

    p_stamp = sub.add_parser("stamp", help="Stamp OKF v0.2 frontmatter and stage pairs")
    p_stamp.add_argument("file", help="Target markdown file")
    p_stamp.add_argument("--type", required=True, dest="okf_type", help="OKF entity type")
    p_stamp.add_argument("--stage", required=True, help="Canonical stage key")
    p_stamp.add_argument("--by", required=True, help="Producer plugin/skill/agent")
    p_stamp.add_argument("--name", help="Human-readable document title")
    p_stamp.add_argument("--description", help="Concise summary")
    p_stamp.add_argument("--status", default="draft", choices=["draft", "stable", "deprecated"])
    p_stamp.add_argument("--source", action="append", dest="sources", help="Upstream relative path")
    p_stamp.add_argument("--stage-pair", action="append", dest="stage_pairs", help="Key=Value pair")
    p_stamp.add_argument("--verified-by", help="Verifier identifier")
    p_stamp.add_argument("--bundle-dir", help="Explicit bundle root directory")

    p_val = sub.add_parser("validate", help="Validate an OKF bundle or file")
    p_val.add_argument("target", help="Bundle directory or markdown file")
    p_val.add_argument("--require-stages", action="store_true", help="Require stages_completed and generated")

    args = parser.parse_args(argv)
    if args.cmd == "init-bundle":
        return init_bundle(Path(args.bundle_dir), args.bundle_id, args.description)
    if args.cmd == "stamp":
        return stamp_file(
            file_path=Path(args.file),
            okf_type=args.okf_type,
            stage=args.stage,
            by=args.by,
            name=args.name,
            description=args.description,
            status=args.status,
            sources=args.sources,
            stage_pairs=args.stage_pairs,
            verified_by=args.verified_by,
            bundle_dir=Path(args.bundle_dir) if args.bundle_dir else None,
        )
    if args.cmd == "validate":
        target_path = Path(args.target).resolve()
        if target_path.is_file():
            res = validate_file(target_path, target_path.parent, require_stages_completed=args.require_stages)
        else:
            res = validate_bundle(target_path, require_stages_completed=args.require_stages)
        for w in res.warnings:
            print(w)
        for e in res.errors:
            print(e)
        return 1 if res.errors else 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
