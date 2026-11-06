# ☕ Bean-Core

> **Canonical Stage Registry, Master Expo Orchestrator, Cross-Cutting Governance & Provenance Engine.**

---

## 🏛️ Architecture & Mission

**`bean-core`** is the central foundation of the Antigravity Specialty Coffee Swarm. It defines:
1. **The Canonical Stage Registry (`stages.yaml`)**: Maps cup sizes (Ristretto, Cortado, Carafe) to pipeline stages and artifacts across `bean-roaster`, `bean-grinder`, `bean-brewer`, and `bean-descale`.
2. **Master Barista Orchestrator (`@expo`)**: The stateless expediter at the pass (`mainAgent: true`). Never touches application source code directly; delegates discovery, specification, coding, and verification to fresh subagents to keep context inside Dex Horthy's **Smart Zone** (<100K tokens).
3. **Cross-Cutting Agents**:
   - **`@threat-modeler`**: ASVS Level 2 security boundary and threat modeling agent.
   - **`@review-arbiter`**: Multi-agent consensus scoring and trade-off reconciliation agent.
4. **Lifecycle Hooks & Guardrails**:
   - `SessionStart`: Automatically rehydrates active `.scratch/<id>/` bundles via `scripts/rehydrate.py`.
   - `PreToolUse`: Blocks destructive git commands (`git push --force`, `git reset --hard`) via `scripts/git_guardrails.py`.
5. **Google Open Knowledge Format (OKF v0.2)**: Provenance stamping (`scripts/okf.py`) ensuring deterministic `stages_completed` pairs, upstream SHA-256 validation, and session retrospective telemetry (`scripts/retro.py`).

---

## 📋 Catalog of Plugins & Capabilities

| Plugin | Theme / Role | Key Stages | Output Artifacts |
| :--- | :--- | :--- | :--- |
| **`bean-core`** | **The Roastery Hub** (Registry, Orchestration & Governance) | Stage 0 (Triage), Cross-cutting Review, Stage 9 (Retro) | `stages.yaml`, `08_RETRO.md` |
| **`bean-roaster`** | **The Roaster** (Product Discovery & Socratic PRD) | Stage 0 (Ideation), Stage 1 (Cupping Form), Stage 3 (PRD) | `00_IDEATION.md`, `01_QUESTIONS.md`, `03_PRD.md` |
| **`bean-grinder`** | **The Grinder** (Legacy Modernization & AST Analysis) | Legacy Assessment, Seam Extraction, Migration Planning | `05_PLAN.md` (Modernization slices) |
| **`bean-brewer`** | **The Brewer** (Implementation, Spec PR & TDD Forge) | Stage 2 (Blind Cupping), Stage 4 (Spec), Stage 5 (Slices), Stage 6 (Council & Spec PR), Stage 7 (TDD), Stage 8 (Verification) | `02_EXTRACTION.md`, `04_SPEC.md`, `05_PLAN.md`, `06_COUNCIL.md`, `06_WALKTHROUGH.md`, `07_VERIFICATION.md` |
| **`bean-descale`** | **The Descaler** (Security Operations & Harness Immunity) | Security Remediation, Attack Trees, Harness Gotcha Immunity | `attack_tree.md`, `.agents/rules/gotchas/` |

---

## 🛠️ Verification & Testing

```bash
# Run bean-core OKF validation and hook test suite
python3 -m unittest discover -s tests -v
```
