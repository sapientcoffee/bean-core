# ☕ Bean-Core: Specialty Coffee Swarm Governance Rules (`AGENTS.md`)

Welcome to **Bean-Core**, the shared orchestration, Open Knowledge Format (OKF v0.2), and safety governance layer for the Antigravity Specialty Coffee Swarm (`bean-roaster`, `bean-grinder`, `bean-brewer`, `bean-cup`, and `bean-descale`).

## 1. Smart Zone Discipline (< 100K Tokens)
- **Head Barista (`@expo`) Delegation:** The orchestrator never writes application source code directly. Delegate discovery, heavy artifact authoring (`ideator` $\rightarrow$ `@product-ideator`, `cupping-form` $\rightarrow$ `@question-formulator`, `research` synthesis $\rightarrow$ `@extraction-synthesizer`, `write-prd` $\rightarrow$ `@prd-author`, `to-spec` & `to-tickets` $\rightarrow$ `@system-design`, `record` $\rightarrow$ `@walkthrough-recorder`), TDD implementation, and verification to isolated subagents (`invoke_subagent`) and deterministic CLI scripts (`scripts/okf.py`, `scripts/plan_lint.py`, `scripts/retro.py`).
- **Capped Subagent Responses:** Subagents write their primary deliverables to OKF-stamped Markdown files and return concise summaries ($\le 300$ words) with file paths and `PASS` / `BLOCKED` status.
- **Session Rehydration:** Persist workflow state in `.scratch/<id>/index.md` and `.scratch/<id>/log.md`. Starting a new conversation automatically rehydrates active bundle context via `scripts/rehydrate.py`.
- **Antigravity Enterprise `/teamwork` Governance:**
  - **Recommended:** Stage 6A (`6a_council`) Carafe Full Council (`@system-design`, `@contract-auditor`, `@code-inspection`, `@threat-modeler`, `@reviewer-product`, `@review-arbiter`), Legacy `adversarial-review` stakeholder negotiation, Stage 7/8 (`7_tdd` / `8_verify`) Carafe parallel Group Head waves, and `bean-descale` security triad (`@vulnerability-scanner`, `@killchain-analyzer`, `@security-remediator`).
  - **Strictly Forbidden:** Stage 2 Blind Cupping (`2_blind_research`), where strict information barriers require isolated `invoke_subagent` calls reading only `.scratch/<id>/01_QUESTIONS.md`.

## 2. Order Triage (`0_triage`)
Every engineering request is classified across two axes before execution:
- **Cup Size:**
  - `ristretto`: Tiny change ($\le 2$ files, clear scope) $\rightarrow$ direct TDD (`0_triage` $\rightarrow$ `7_tdd` $\rightarrow$ `8_verify`).
  - `cortado`: Single-session feature ($\le 4$ slices) $\rightarrow$ `.scratch/<id>/` OKF bundle + `RequestFeedback` artifact gate.
  - `carafe`: Multi-session epic or high blast radius $\rightarrow$ Spec PR review gate + GitHub Sub-Issues state machine.
- **Origin:** `greenfield` (`0_ideation`), `brownfield` (`1_questions` $\rightarrow$ `2_blind_research`), or `legacy` (`1_assess`).

## 3. Open Knowledge Format (OKF v0.2) Invariants
- **Deterministic Stamping:** Never hand-write timestamps, SHA-256 hashes, or `stages_completed` maps. Always use `python3 scripts/okf.py init-bundle` and `python3 scripts/okf.py stamp`.
- **Filename Parity:** Every OKF entity file's YAML frontmatter `id` must match its filename stem (`04_SPEC.md` $\rightarrow$ `id: 04_SPEC`), except root `index.md` (`type: bundle`).
- **Relative Paths Only:** Cross-document references in `sources`, `inputs`, `outputs`, and `related_tables` must use relative paths without leading slashes.

## 4. Safety & Quality Guardrails
- **Git Guardrails (`scripts/git_guardrails.py`):** Destructive git commands (`git push --force` without `--force-with-lease`, `git reset --hard`, `git clean -f`, and `git branch -D main|master`) are strictly denied.
- **Backflush Retrospective (`scripts/retro.py`):** Conclude `cortado` and `carafe` workflows by mining `transcript.jsonl` into `08_RETRO.md` to audit error steps, 3+ tool retry streaks, and Smart Zone compliance.
