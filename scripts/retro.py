#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""Backflush Transcript Miner (`scripts/retro.py`).

Parses `transcript.jsonl` to measure:
- Total steps and tool calls (by tool name and overall)
- `ERROR` status steps
- Consecutive 3+ tool retry streaks (same tool invoked >= 3 times in a row)
- Total transcript bytes and approximate tokens (`bytes // 4`)
- Smart Zone compliance (`< 100,000` tokens)
Writes an OKF v0.2-stamped `08_RETRO.md` report into the target bundle directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import okf  # noqa: E402

SMART_ZONE_TOKEN_LIMIT = 100_000


def extract_tool_names(step: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    tool_calls = step.get("tool_calls") or step.get("toolCalls")
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if isinstance(tc, dict):
                name = (
                    tc.get("name")
                    or tc.get("tool_name")
                    or tc.get("toolName")
                    or (tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}).get("name")
                )
                if name:
                    names.append(str(name))
            elif isinstance(tc, str):
                names.append(tc)
    single_tc = step.get("toolCall") or step.get("tool_call")
    if isinstance(single_tc, dict):
        name = single_tc.get("name") or single_tc.get("tool_name")
        if name:
            names.append(str(name))
    if not names and isinstance(step.get("tool_name"), str):
        names.append(step["tool_name"])
    return names


def analyze_transcript(transcript_path: Path) -> Dict[str, Any]:
    if not transcript_path.is_file():
        return {
            "total_steps": 0,
            "total_tool_calls": 0,
            "tool_counts": {},
            "error_steps": 0,
            "error_step_indices": [],
            "retry_streaks": [],
            "total_bytes": 0,
            "approx_tokens": 0,
            "smart_zone_compliant": True,
        }

    raw_bytes = transcript_path.read_bytes()
    total_bytes = len(raw_bytes)
    approx_tokens = total_bytes // 4

    total_steps = 0
    total_tool_calls = 0
    tool_counts: Counter[str] = Counter()
    error_steps = 0
    error_step_indices: List[int] = []
    tool_sequence: List[str] = []

    for line_idx, line in enumerate(raw_bytes.decode("utf-8", errors="replace").splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            step = json.loads(stripped)
        except Exception:
            continue
        if not isinstance(step, dict):
            continue

        total_steps += 1
        step_idx = step.get("step_index", line_idx)
        status = str(step.get("status", "")).upper()
        if status == "ERROR" or step.get("error"):
            error_steps += 1
            error_step_indices.append(int(step_idx) if isinstance(step_idx, int) else line_idx)

        t_names = extract_tool_names(step)
        for tn in t_names:
            total_tool_calls += 1
            tool_counts[tn] += 1
            tool_sequence.append(tn)

    retry_streaks: List[Dict[str, Any]] = []
    if tool_sequence:
        cur_tool = tool_sequence[0]
        cur_count = 1
        for tn in tool_sequence[1:]:
            if tn == cur_tool:
                cur_count += 1
            else:
                if cur_count >= 3:
                    retry_streaks.append({"tool": cur_tool, "count": cur_count})
                cur_tool = tn
                cur_count = 1
        if cur_count >= 3:
            retry_streaks.append({"tool": cur_tool, "count": cur_count})

    smart_zone_compliant = approx_tokens < SMART_ZONE_TOKEN_LIMIT

    return {
        "total_steps": total_steps,
        "total_tool_calls": total_tool_calls,
        "tool_counts": dict(tool_counts),
        "error_steps": error_steps,
        "error_step_indices": error_step_indices,
        "retry_streaks": retry_streaks,
        "total_bytes": total_bytes,
        "approx_tokens": approx_tokens,
        "smart_zone_compliant": smart_zone_compliant,
    }


def generate_retro_markdown(metrics: Dict[str, Any]) -> str:
    sz_badge = "PASS (< 100K tokens)" if metrics["smart_zone_compliant"] else "EXCEEDED (>= 100K tokens)"
    streaks = metrics["retry_streaks"]
    if streaks:
        streak_lines = [f"- `{s['tool']}`: **{s['count']} consecutive calls**" for s in streaks]
    else:
        streak_lines = ["- None detected (0 streaks >= 3 consecutive calls)."]

    tool_rows = [
        f"| `{tool}` | {count} |"
        for tool, count in sorted(metrics["tool_counts"].items(), key=lambda x: (-x[1], x[0]))
    ]
    if not tool_rows:
        tool_rows = ["| *(none)* | 0 |"]

    body = "\n".join(
        [
            "",
            "# 08_RETRO: Backflush Session Retrospective",
            "",
            "## 1. Trajectory & Smart Zone Summary",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| **Total Steps** | `{metrics['total_steps']}` |",
            f"| **Total Tool Calls** | `{metrics['total_tool_calls']}` |",
            f"| **ERROR Steps** | `{metrics['error_steps']}` |",
            f"| **3+ Tool Retry Streaks** | `{len(streaks)}` |",
            f"| **Transcript Size (Bytes)** | `{metrics['total_bytes']}` |",
            f"| **Approx Tokens (~bytes/4)** | `{metrics['approx_tokens']}` |",
            f"| **Smart Zone Compliance (<100K)** | **{sz_badge}** |",
            "",
            "## 2. Consecutive Tool Retry Streaks (3+)",
            "",
            *streak_lines,
            "",
            "## 3. Tool Call Breakdown",
            "",
            "| Tool | Calls |",
            "| :--- | :--- |",
            *tool_rows,
            "",
        ]
    )
    return body


def write_retro_report(
    transcript_path: Path,
    bundle_dir: Path,
    output_file: Path | None = None,
    by: str = "bean-core/retro",
) -> Dict[str, Any]:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    if not (bundle_dir / "index.md").exists():
        okf.init_bundle(bundle_dir)

    metrics = analyze_transcript(transcript_path)
    body = generate_retro_markdown(metrics)
    retro_path = output_file or (bundle_dir / "08_RETRO.md")
    retro_path.write_text(body, encoding="utf-8")

    okf.stamp_file(
        file_path=retro_path,
        okf_type="retrospective",
        stage="9_retro",
        by=by,
        name="Backflush Retrospective",
        description="Automated transcript telemetry, retry streak analysis, and Smart Zone audit.",
        status="stable",
        stage_pairs={
            "smart_zone": "pass" if metrics["smart_zone_compliant"] else "exceeded",
            "error_steps": str(metrics["error_steps"]),
            "retry_streaks": str(len(metrics["retry_streaks"])),
        },
        bundle_dir=bundle_dir,
    )
    metrics["retro_path"] = str(retro_path)
    return metrics


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backflush transcript miner (08_RETRO.md).")
    parser.add_argument("--transcript", required=True, help="Path to transcript.jsonl")
    parser.add_argument("--bundle-dir", default=".", help="Target OKF bundle directory")
    parser.add_argument("--output", help="Optional explicit path for 08_RETRO.md")
    parser.add_argument("--json", action="store_true", help="Print metrics as JSON")
    args = parser.parse_args(argv)

    t_path = Path(args.transcript)
    b_dir = Path(args.bundle_dir)
    out_path = Path(args.output) if args.output else None

    metrics = write_retro_report(t_path, b_dir, output_file=out_path)
    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print(
            f"Backflush complete: {metrics['total_steps']} steps, "
            f"{metrics['total_tool_calls']} tool calls, "
            f"{metrics['error_steps']} errors, "
            f"{len(metrics['retry_streaks'])} retry streaks -> {metrics['retro_path']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
