#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""PreToolUse Git Guardrails Hook (`scripts/git_guardrails.py`).

Reads hook JSON from stdin (`tool_input.CommandLine`, `toolCall.args.CommandLine`, or `command`)
and denies destructive git operations:
- `git push --force` / `git push -f` (except `--force-with-lease` or `--force-if-includes`)
- `git reset --hard`
- `git clean -f` (e.g. `-f`, `-fd`, `-fx`, `-df`, `--force`)
- `git branch -D main|master`
Returns `{"decision": "deny", "reason": "..."}` or `{"decision": "allow"}`.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict


def extract_command(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    if isinstance(payload.get("command"), str):
        return payload["command"]
    if isinstance(payload.get("CommandLine"), str):
        return payload["CommandLine"]
    tool_input = payload.get("tool_input") or payload.get("toolInput")
    if isinstance(tool_input, dict):
        for k in ("CommandLine", "command", "cmd"):
            if isinstance(tool_input.get(k), str):
                return tool_input[k]
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        args = tool_call.get("args") or tool_call.get("arguments")
        if isinstance(args, dict):
            for k in ("CommandLine", "command", "cmd"):
                if isinstance(args.get(k), str):
                    return args[k]
    return ""


def evaluate_command(cmd: str) -> Dict[str, str]:
    if not cmd or "git" not in cmd:
        return {"decision": "allow"}

    # Split compound shell commands so each segment is checked independently
    segments = re.split(r"(?:&&|\|\||;|\n|\|)", cmd)
    for seg in segments:
        s = seg.strip()
        if not s:
            continue

        # 1. git push --force / -f (allow --force-with-lease and --force-if-includes)
        if re.search(r"\bgit\b(?:\s+-\S+(?:\s+\S+)?)?\s+push\b", s):
            sanitized = re.sub(r"--force-with-lease(?:=\S+)?", "", s)
            sanitized = re.sub(r"--force-if-includes", "", sanitized)
            if re.search(r"(?:^|\s)(?:--force|-f)(?:\s|$)", sanitized) or re.search(
                r"(?:^|\s)\+[a-zA-Z0-9_./-]+:[a-zA-Z0-9_./-]+", sanitized
            ):
                return {
                    "decision": "deny",
                    "reason": "Destructive `git push --force` is blocked by Bean-Core guardrails. Use `--force-with-lease` instead.",
                }

        # 2. git reset --hard
        if re.search(r"\bgit\b(?:\s+-\S+(?:\s+\S+)?)?\s+reset\b.*\s--hard(?:\s|$)", s):
            return {
                "decision": "deny",
                "reason": "Destructive `git reset --hard` is blocked by Bean-Core guardrails to prevent uncommitted work loss.",
            }

        # 3. git clean -f / -fd / -fx / --force (allow -n / --dry-run)
        if re.search(r"\bgit\b(?:\s+-\S+(?:\s+\S+)?)?\s+clean\b", s):
            if not re.search(r"(?:^|\s)(?:-n|--dry-run)(?:\s|$)", s):
                if re.search(r"(?:^|\s)(?:--force|-[a-zA-Z]*f[a-zA-Z]*)(?:\s|$)", s):
                    return {
                        "decision": "deny",
                        "reason": "Destructive `git clean -f` is blocked by Bean-Core guardrails.",
                    }

        # 4. git branch -D main|master (or --delete --force main|master)
        if re.search(r"\bgit\b(?:\s+-\S+(?:\s+\S+)?)?\s+branch\b", s):
            if re.search(r"(?:^|\s)-D\s+(?:.*\s)?(?:main|master)(?:\s|$)", s) or (
                re.search(r"--delete", s)
                and re.search(r"--force|-f", s)
                and re.search(r"\b(?:main|master)\b", s)
            ):
                return {
                    "decision": "deny",
                    "reason": "Deleting protected branch `main` or `master` (`git branch -D main|master`) is blocked by Bean-Core guardrails.",
                }

    return {"decision": "allow"}


def main() -> int:
    raw = ""
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read().strip()
        except Exception:
            raw = ""

    if not raw:
        print(json.dumps({"decision": "allow"}))
        return 0

    try:
        payload = json.loads(raw)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return 0

    cmd = extract_command(payload)
    verdict = evaluate_command(cmd)
    print(json.dumps(verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())
