---
name: retro
description: Stage 9 Backflush Retrospective skill. Mines conversation transcripts (transcript.jsonl) via scripts/retro.py to measure steps, tool calls, ERROR steps, consecutive 3+ tool retry streaks, token budget, and Smart Zone compliance (<100K tokens), emitting an OKF-stamped 08_RETRO.md report.
---

<!--
Copyright 2026 Google LLC
Licensed under the Apache License, Version 2.0
-->

# ☕ Skill: Stage 9 Backflush Retrospective (`bean-core/skills/retro`)

You are executing **Backflush** (`9_retro`). Just as a barista backflushes the group head with detergent to clear coffee oils and residue after service, this skill mines the session's `transcript.jsonl` to surface harness friction, tool retry loops, and context bloat, producing a deterministic `08_RETRO.md` artifact.

---

## 1. Metrics Audited by `scripts/retro.py`

1. **Trajectory Volume**: Total steps, tool calls by name, and `ERROR` status steps.
2. **Retry Streak Detection**: Identifies consecutive 3+ calls to the same tool (or repeated failures), signaling missing CLI affordances or brittle prompts.
3. **Context & Smart Zone Compliance**: Computes total transcript bytes and approximate token utilization ($\approx \text{bytes} / 4$), verifying whether the orchestrator remained inside Dex Horthy's **Smart Zone** ($< 100\text{K}$ tokens).
4. **OKF v0.2 Provenance**: Stamps `08_RETRO.md` with `type: retrospective`, `stage: 9_retro`, `generated`, and `stages_completed`, and updates the bundle's `index.md` and `log.md`.

---

## 2. Operational Protocol

1. **Run the Deterministic Transcript Miner**:
   ```bash
   python3 scripts/retro.py \
     --transcript "<path-to-transcript.jsonl>" \
     --bundle-dir "plans/<id>"
   ```
2. **Validate the Bundle**:
   ```bash
   python3 scripts/okf.py validate "plans/<id>" --require-stages
   ```
3. **Recommend Durable Improvements**:
   - If `08_RETRO.md` flags any `ERROR` steps or 3+ consecutive tool retry streaks, formulate a concise rule or gotcha and recommend the `/learn` slash command to the user.
