#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""Deterministic OKF v0.2 Frontmatter Stamper & Bundle Initializer (`okf_stamp.py`).

Ensures LLMs never hallucinate timestamps, SHA-256 hashes, or out-of-sync `id` stems.
Supports:
- `init-bundle`: Creates `<bundle_dir>/index.md` (`type: bundle`, `okf_version: "0.2"`) and `log.md`.
- `stamp`: Injects or updates YAML frontmatter on an OKF Markdown file (`id` = filename stem,
  `type`, `name`, `description`, `status`, `stage`, `generated: {by, at}`, `verified`, `sources`
  with real file mtime + sha256, and `stages_completed` key-value pairs) and appends to `log.md`.
"""

import argparse
import datetime
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def file_mtime_iso(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def split_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    lines = content.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                raw = "".join(lines[1:idx])
                body = "".join(lines[idx + 1 :])
                data = yaml.safe_load(raw)
                return (data if isinstance(data, dict) else {}), body
    return {}, content


def render_markdown(frontmatter: Dict[str, Any], body: str) -> str:
    fm_str = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
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
        fm, _ = split_frontmatter(index_path.read_text(encoding="utf-8"))
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
        pfm, _ = split_frontmatter(p.read_text(encoding="utf-8"))
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


def init_bundle(bundle_dir: Path, bundle_id: str | None, description: str | None) -> int:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    refresh_index(bundle_dir, bundle_id=bundle_id, description=description)
    append_log(bundle_dir, "0_triage", "bean-core/okf_stamp", "index.md", "Initialized OKF v0.2 bundle")
    print(f"✅ Initialized OKF bundle at {bundle_dir}")
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
    stage_pairs: List[str] | None = None,
    verified_by: str | None = None,
    bundle_dir: Path | None = None,
) -> int:
    b_dir = bundle_dir or file_path.parent
    b_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now_iso()

    if file_path.exists():
        existing_fm, body = split_frontmatter(file_path.read_text(encoding="utf-8"))
    else:
        existing_fm, body = {}, f"\n# {name or file_path.stem}\n"

    fm: Dict[str, Any] = {}
    # Force id == filename stem for strict OKF parity
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
    if sources:
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
    if stage_pairs:
        for pair in stage_pairs:
            if "=" in pair:
                k, v = pair.split("=", 1)
                stages_map[k.strip()] = v.strip()
    stages_map[stage] = f"{by} ({now})"
    fm["stages_completed"] = stages_map

    # Preserve extra domain keys (e.g. test_seams, out_of_scope)
    reserved = {
        "id", "type", "name", "description", "status", "stage",
        "generated", "verified", "sources", "stages_completed",
    }
    for k, v in existing_fm.items():
        if k not in reserved:
            fm[k] = v

    file_path.write_text(render_markdown(fm, body), encoding="utf-8")
    refresh_index(b_dir)
    append_log(b_dir, stage, by, file_path.name, f"Stamped {file_path.name} [{fm['status']}]")
    print(f"✅ Stamped OKF metadata on {file_path}")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OKF v0.2 deterministic stamper and bundle initializer.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-bundle", help="Initialize an OKF bundle root with index.md and log.md")
    p_init.add_argument("bundle_dir", help="Bundle directory path")
    p_init.add_argument("--id", dest="bundle_id", help="Bundle identifier (defaults to directory name)")
    p_init.add_argument("--description", help="Bundle overview description")

    p_stamp = sub.add_parser("stamp", help="Stamp OKF v0.2 frontmatter and stage pairs onto a markdown file")
    p_stamp.add_argument("file", help="Target markdown file")
    p_stamp.add_argument("--type", required=True, dest="okf_type", help="OKF entity type (e.g. specification, plan)")
    p_stamp.add_argument("--stage", required=True, help="Canonical stage key (e.g. 4_spec)")
    p_stamp.add_argument("--by", required=True, help="Producer plugin/skill/agent (e.g. bean-brewer/to-spec)")
    p_stamp.add_argument("--name", help="Human-readable document title")
    p_stamp.add_argument("--description", help="Concise summary")
    p_stamp.add_argument("--status", default="draft", choices=["draft", "stable", "deprecated"])
    p_stamp.add_argument("--source", action="append", dest="sources", help="Relative path to upstream source file")
    p_stamp.add_argument("--stage-pair", action="append", dest="stage_pairs", help="Key=Value stage provenance pair")
    p_stamp.add_argument("--verified-by", help="Optional verifier identifier to append to verified[]")
    p_stamp.add_argument("--bundle-dir", help="Explicit bundle root directory")

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
    return 1


if __name__ == "__main__":
    sys.exit(main())
