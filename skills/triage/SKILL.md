---
name: triage
description: Stage 0 Order Triage skill for the Specialty Coffee Swarm. Classifies incoming engineering requests across Cup-Size (ristretto, cortado, carafe) and Origin (greenfield, brownfield, legacy), initializes an OKF v0.2 bundle in .scratch/<id>/, and routes execution according to stages.yaml.
---

<!--
Copyright 2026 Google LLC
Licensed under the Apache License, Version 2.0
-->

# ☕ Skill: Stage 0 Order Triage (`bean-core/skills/triage`)

You are executing **Order Triage** (`0_triage`). Before any research, specification, or coding begins, classify the incoming request across two orthogonal axes—**Cup Size** and **Origin**—and initialize the canonical OKF v0.2 bundle.

---

## 1. Classification Matrix

### Axis A: Cup Size (Blast Radius & Governance Gate)
| Cup Size | Criteria | Gate | Stage Pipeline |
| :--- | :--- | :--- | :--- |
| **`ristretto`** | Tiny change ($\le 2$ files, $\le 1$ context window, unambiguous requirements) | `direct_commit` | `0_triage` $\rightarrow$ `7_tdd` $\rightarrow$ `8_verify` |
| **`cortado`** | Small-to-medium feature (single-session planning, $\le 4$ vertical slices) | `artifact_gate` (`RequestFeedback`) | `0_triage` $\rightarrow$ `1_questions` $\rightarrow$ `2_blind_research` $\rightarrow$ `3_grill_and_prd` $\rightarrow$ `4_spec` $\rightarrow$ `5_plan` $\rightarrow$ `6a_council` $\rightarrow$ `6b_promote` $\rightarrow$ `7_tdd` $\rightarrow$ `8_verify` $\rightarrow$ `9_retro` |
| **`carafe`** | Multi-session epic, cross-cutting architecture, or high blast radius | `spec_pr` + GitHub Sub-Issues | Full `0_triage` .. `9_retro` pipeline with Spec PR review gate |

### Axis B: Origin (Codebase Maturity & Entry Stage)
| Origin | Criteria | Entry Stage | Target Plugin |
| :--- | :--- | :--- | :--- |
| **`greenfield`** | New repository, standalone module, or net-new product concept | `0_ideation` (`00_IDEATION.md`) | `bean-roaster` |
| **`brownfield`** | Feature or bugfix inside an active, structured codebase | `1_questions` (`01_QUESTIONS.md`) | `bean-roaster` $\rightarrow$ `bean-brewer` |
| **`legacy`** | Undocumented, brittle, or tangled subsystem needing modernization | `1_assess` | `bean-grinder` |

---

## 2. Operational Steps

1. **Clarify Ambiguity**:
   - If the Cup Size or Origin is ambiguous, call `ask_question` with the recommended classification listed first (`(Recommended)`).
2. **Initialize Ephemeral OKF v0.2 Bundle**:
   - For `cortado` and `carafe` orders (or whenever an artifact bundle is needed), run:
     ```bash
     python3 scripts/okf.py init-bundle ".scratch/<id>" --id "<id>" --description "<concise summary>"
     ```
   - Stamp the triage decision onto `.scratch/<id>/index.md`:
     ```bash
     python3 scripts/okf.py stamp ".scratch/<id>/index.md" \
       --type bundle \
       --stage 0_triage \
       --by "bean-core/triage" \
       --stage-pair "cup_size=<ristretto|cortado|carafe>" \
       --stage-pair "origin=<greenfield|brownfield|legacy>"
     ```
3. **Route to Next Stage**:
   - Follow `stages.yaml` to invoke the entry skill or subagent for the selected `cup_size` and `origin`.
