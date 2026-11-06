# ☕ Bean-Core Architecture

> The plain-Markdown companion to the **[interactive architecture explorer](index.html)**.
> The explorer lets you drill from the swarm overview down to individual functions and step through each runtime flow.
> This document covers the same material in a form that renders on GitHub.

**Contents**

1. [Where bean-core sits in the swarm](#1-where-bean-core-sits-in-the-swarm)
2. [Component layers](#2-component-layers)
3. [The pipeline: cup sizes, origins and gates](#3-the-pipeline-cup-sizes-origins-and-gates)
4. [Runtime flows](#4-runtime-flows)
5. [OKF v0.2 bundles and frontmatter](#5-okf-v02-bundles-and-frontmatter)
6. [Git guardrails](#6-git-guardrails)
7. [Council consensus](#7-council-consensus)
8. [Script and function reference](#8-script-and-function-reference)
9. [Known gaps](#9-known-gaps)

---

## 1. Where bean-core sits in the swarm

bean-core is the shared hub of the Antigravity Specialty Coffee Swarm. It owns the stage registry, the orchestrator persona, the lifecycle hooks and the OKF tooling. The other plugins provide the stage skills.

```mermaid
flowchart LR
    core["bean-core: registry, expo, hooks, OKF"]
    roaster["bean-roaster: ideation, questions, grill, PRD"]
    grinder["bean-grinder: legacy assessment"]
    brewer["bean-brewer: research, spec, plan, council, TDD, verify"]
    descale["bean-descale: security remediation"]
    cup["bean-cup: dashboard, kanban, state scanner"]

    core -->|"stages.yaml routes to"| roaster
    core -->|"legacy origin"| grinder
    core -->|"stages 2, 4 to 8"| brewer
    core -.->|"security follow-up"| descale
    cup -.->|"reads .scratch bundles"| core
```

| Plugin | Role | Stages it owns |
| :--- | :--- | :--- |
| **bean-core** | Registry, orchestration, governance | `0_triage`, `9_retro`, cross-cutting agents |
| **bean-roaster** | Product discovery and PRD | `0_ideation`, `1_questions`, `3_grill_and_prd` |
| **bean-grinder** | Legacy modernisation | `1_assess` (legacy entry, see [gap 3](#9-known-gaps)) |
| **bean-brewer** | Spec, slices, council and TDD | `2_blind_research`, `4_spec`, `5_plan`, `6a_council`, `6b_promote`, `7_tdd`, `8_verify` |
| **bean-descale** | Security operations | Attack trees, remediation, harness gotchas |
| **bean-cup** | Visual dashboard | Reads bundle state; owns no stage |

---

## 2. Component layers

```mermaid
flowchart TD
    subgraph L1["Layer 1: Registry"]
        stages["stages.yaml"]
    end
    subgraph L2["Layer 2: Agents"]
        expo["@expo (mainAgent)"]
        threat["@threat-modeler"]
        arbiter["@review-arbiter"]
    end
    subgraph L3["Layer 3: Skills"]
        triage["triage"]
        retroSkill["retro"]
    end
    subgraph L4["Layer 4: Hooks"]
        hooks["hooks.json"]
    end
    subgraph L5["Layer 5: Scripts"]
        okf["okf.py"]
        rehydrate["rehydrate.py"]
        guard["git_guardrails.py"]
        retroPy["retro.py"]
    end
    subgraph L6["Layer 6: Rules"]
        rules["rules/AGENTS.md"]
    end
    subgraph L7["Layer 7: Tests and install"]
        tests["tests/"]
        install["install.sh"]
    end

    expo -->|"reads"| stages
    triage -->|"init-bundle, stamp"| okf
    retroSkill -->|"runs"| retroPy
    retroSkill -->|"stamps"| okf
    hooks -->|"SessionStart"| rehydrate
    hooks -->|"PreToolUse"| guard
    hooks -->|"PostToolUse"| okf
    tests -->|"checks"| okf
    tests -->|"checks"| stages
```

| Layer | Files | Purpose |
| :--- | :--- | :--- |
| Registry | `stages.yaml` | Canonical map of cup sizes, origins and stages (plugin, skill, artifact, OKF type, next stages). |
| Agents | `agents/expo.md`, `agents/threat-modeler.md`, `agents/review-arbiter.md` | `@expo` is the stateless orchestrator. It delegates all work to subagents to stay inside the Smart Zone (< 100K tokens). The other two are cross-cutting reviewers. |
| Skills | `skills/triage/SKILL.md`, `skills/retro/SKILL.md` | Stage 0 classification and Stage 9 retrospective. |
| Hooks | `hooks.json` | Wires the scripts into `SessionStart`, `PreToolUse` and `PostToolUse`. |
| Scripts | `scripts/*.py` | Deterministic, standard-library Python (PyYAML optional) for OKF stamping, validation, rehydration, guardrails and retros. |
| Rules | `rules/AGENTS.md` | Always-on governance loaded into every conversation. |
| Tests and install | `tests/`, `install.sh` | Unit tests and a copy-based installer. |

---

## 3. The pipeline: cup sizes, origins and gates

Every request is classified on two axes: **cup size** (how big) and **origin** (where it starts).

| Cup size | Scope | Stages | Gate |
| :--- | :--- | :--- | :--- |
| `ristretto` | ≤ 2 files, clear requirements | `0_triage` → `7_tdd` → `8_verify` | `direct_commit` |
| `cortado` | Single-session feature, ≤ 4 slices | All 11 stages | `artifact_gate` (RequestFeedback artifact) |
| `carafe` | Multi-session epic or high blast radius | All 11 stages | `spec_pr` (Spec PR plus GitHub Sub-Issues) |

| Origin | Entry stage | Plugin |
| :--- | :--- | :--- |
| `greenfield` | `0_ideation` | bean-roaster |
| `brownfield` | `1_questions` | bean-roaster |
| `legacy` | `1_assess` | bean-grinder |

```mermaid
flowchart LR
    T["0_triage: Order Triage"] -->|"ristretto"| TDD
    T -->|"greenfield"| I["0_ideation: Green Bean Selection"]
    T -->|"brownfield"| Q["1_questions: Cupping Form"]
    T -.->|"legacy"| A["1_assess: bean-grinder"]
    I --> G
    Q --> R["2_blind_research: Blind Cupping"]
    R --> G["3_grill_and_prd: Dial-In"]
    G --> S["4_spec: Recipe Card"]
    S --> P["5_plan: Vertical Slices"]
    P --> C["6a_council: Q-Grader Panel"]
    C --> PR["6b_promote: Calling the Order"]
    PR --> TDD["7_tdd: Group Heads"]
    TDD --> V["8_verify: Tasting at the Pass"]
    V --> RT["9_retro: Backflush"]
```

Notes:

- `1_assess` is referenced by `origins.legacy` and `0_triage.next` but has no entry under `stages:`. The diagram draws it dashed.
- Greenfield skips `1_questions` and `2_blind_research`, because `0_ideation.next` is `3_grill_and_prd`.
- Stages `0` to `6b` write to the ephemeral bundle (`.scratch/<id>/`). Stages `8` and `9` write to durable plans (`plans/`).
- `7_tdd` runs up to 3 parallel `code-implementation` workers in `share` workspace mode.

---

## 4. Runtime flows

### 4.1 Order lifecycle

```mermaid
sequenceDiagram
    actor User
    participant Expo as @expo
    participant Triage as triage skill
    participant OKF as okf.py
    participant Stage as stage skill / subagent
    participant Retro as retro skill

    User->>Expo: Engineering request
    Expo->>Triage: Classify cup size and origin
    Triage->>OKF: init-bundle .scratch/BUNDLE_ID
    OKF-->>Triage: index.md and log.md
    loop Each stage in stages.yaml
        Expo->>Stage: invoke_subagent with stage inputs
        Stage->>OKF: stamp artifact --type --stage --by
        OKF-->>Stage: frontmatter, index refresh, log entry
        Stage-->>Expo: Summary of 300 words or fewer, PASS or BLOCKED
    end
    Expo->>Retro: 9_retro (cortado and carafe)
    Retro->>OKF: retro.py stamps 08_RETRO.md
    Expo-->>User: Delivered change and retro
```

### 4.2 SessionStart: rehydration

```mermaid
sequenceDiagram
    participant Host as Antigravity
    participant Hook as SessionStart hook
    participant RH as rehydrate.py
    participant FS as .scratch/*/index.md

    Host->>Hook: New conversation
    Hook->>RH: python3 ./scripts/rehydrate.py (15s timeout)
    Note over RH: workspaces from --workspace, stdin workspacePaths / workspacePath / cwd, else os.getcwd
    RH->>FS: glob */index.md in each workspace
    FS-->>RH: frontmatter (id, name, stage, status)
    alt Bundles found
        RH-->>Host: JSON injectSteps system message
    else No bundles
        RH-->>Host: empty JSON
    end
```

### 4.3 PreToolUse: git guardrails

```mermaid
sequenceDiagram
    participant Agent
    participant Hook as PreToolUse hook (run_command)
    participant GG as git_guardrails.py

    Agent->>Hook: run_command payload
    Hook->>GG: JSON on stdin
    GG->>GG: extract_command, then split into segments on shell separators
    GG->>GG: evaluate_command on each segment
    alt Destructive pattern matched
        GG-->>Agent: decision deny with reason
    else Safe
        GG-->>Agent: decision allow
    end
```

### 4.4 PostToolUse: advisory validation

```mermaid
sequenceDiagram
    participant Agent
    participant Hook as PostToolUse hook
    participant OKF as okf.py validate .scratch

    Agent->>Hook: write_file, edit_file and similar
    Hook->>OKF: validate .scratch
    OKF-->>Hook: errors and warnings
    Note over Hook: stderr discarded and exit forced to 0, so the hook never blocks
```

### 4.5 `okf.py stamp`

```mermaid
sequenceDiagram
    participant Caller
    participant Stamp as stamp_file
    participant FM as extract_frontmatter
    participant Idx as refresh_index
    participant Log as append_log

    Caller->>Stamp: file, --type, --stage, --by, --source...
    Stamp->>FM: read existing frontmatter and body
    Stamp->>Stamp: id = file stem, generated = {by, at}
    Stamp->>Stamp: hash each source (sha256, last_modified)
    Stamp->>Stamp: stages_completed[stage] = "by (timestamp)"
    Stamp->>Stamp: render_markdown and write file
    opt index.md exists in bundle
        Stamp->>Idx: rebuild artifact table
    end
    opt log.md exists in bundle
        Stamp->>Log: append stage, producer, file
    end
```

### 4.6 Council (Stage 6A)

```mermaid
sequenceDiagram
    participant Expo as @expo
    participant Council as plan-council skill (bean-brewer)
    participant Rev as Reviewers
    participant Arb as @review-arbiter

    Expo->>Council: 05_PLAN.md
    Council->>Council: plan_lint.py pre-lint
    Council->>Rev: code-inspection, contract-auditor, threat-modeler, reviewer-product
    Rev-->>Arb: Findings by severity
    Arb->>Arb: score = max(0, 100 - 25C - 10H - 3M - 1L)
    alt score >= 90, C = 0, H = 0
        Arb-->>Council: CONVERGED
    else Round < 3
        Arb-->>Council: NEEDS_REVISION and patch proposals
    else Round 3
        Arb-->>Council: CIRCUIT_BREAKER_TRIGGERED
    end
    Council-->>Expo: 06_COUNCIL.md
```

### 4.7 Retro (Stage 9)

```mermaid
sequenceDiagram
    participant Skill as retro skill
    participant R as retro.py
    participant T as transcript.jsonl
    participant OKF as okf.py

    Skill->>R: --transcript path --bundle-dir dir
    R->>T: read every JSONL step
    R->>R: count steps, tool calls, ERROR steps
    R->>R: detect 3+ identical tool streaks
    R->>R: approx tokens = bytes / 4, Smart Zone < 100K
    R->>R: write 08_RETRO.md
    R->>OKF: stamp_file (retrospective, 9_retro, smart_zone and error pairs)
    R-->>Skill: metrics and retro path
```

---

## 5. OKF v0.2 bundles and frontmatter

A bundle is a directory, normally `.scratch/<id>/`, containing:

| File | Role |
| :--- | :--- |
| `index.md` | Bundle root, `type: bundle`. `refresh_index` rebuilds its artifact table on every stamp. |
| `log.md` | Append-only audit log written by `append_log`. |
| `NN_*.md` | Stage artifacts. Frontmatter `id` must equal the filename stem. |

Example frontmatter produced by `okf.py stamp`:

```yaml
---
id: 04_SPEC
type: specification
name: Recipe Card
description: Recipe Card (4_spec)
status: draft
stage: 4_spec
generated:
  by: bean-brewer/to-spec
  at: 2026-11-06T17:00:00Z
sources:
  - id: 03_PRD
    resource: 03_PRD.md
    last_modified: 2026-11-06T16:40:00Z
    sha256: 9f2c...
stages_completed:
  3_grill_and_prd: bean-roaster/write-prd (2026-11-06T16:40:00Z)
  4_spec: bean-brewer/to-spec (2026-11-06T17:00:00Z)
---
```

Invariants checked by `okf.py validate`:

- **Filename parity.** `id` must match the filename stem. Only the root `index.md` is exempt, and it must have `type: bundle`.
- **`type` is required.**
- **Relative paths only.** An absolute path in `sources[].resource`, `inputs`, `outputs` or `related_tables` is an error. An unresolvable relative path is a warning.
- **With `--require-stages`.** `stages_completed` must be non-empty, and `generated` must contain both `by` and `at`.
- **Never hand-write** timestamps, hashes or `stages_completed`. Always use `okf.py init-bundle` and `okf.py stamp`.

---

## 6. Git guardrails

`scripts/git_guardrails.py` splits a command on `&&`, `||`, `;`, `|` and newlines, then checks each segment:

| Rule | Denied | Allowed |
| :--- | :--- | :--- |
| Force push | `push --force`, `push -f`, `push origin +src:dst` | `--force-with-lease`, `--force-if-includes` |
| Hard reset | `reset ... --hard` | `reset --soft`, `reset --mixed` |
| Clean | `clean -f`, `-fd`, `-fx`, `--force` | Anything with `-n` or `--dry-run` |
| Protected branch delete | `branch -D main\|master`, `branch --delete --force main\|master` | Deleting any other branch |

Global options between `git` and the subcommand (for example `git -C repo push -f`) are also caught. You can try commands in the **Playground** view of the [interactive explorer](index.html#playground). It runs a JavaScript port of `evaluate_command`.

---

## 7. Council consensus

`@review-arbiter` scores each review round:

$$\text{score} = \max(0,\ 100 - 25C - 10H - 3M - 1L)$$

| Verdict | Condition |
| :--- | :--- |
| `CONVERGED` | score ≥ 90, no Critical and no High findings |
| `NEEDS_REVISION` | score < 90, or Critical/High findings remain (up to round 3) |
| `CIRCUIT_BREAKER_TRIGGERED` | Round 3 reached without convergence; escalate to the Stage 6B human gate |

The arbiter only proposes patches. It never edits `05_PLAN.md` itself.

---

## 8. Script and function reference

All line numbers refer to `main`. The interactive explorer links each function to its line range on GitHub, and `tests/test_docs.py` fails if a referenced line stops being the matching `def`.

### `scripts/okf.py`

```bash
python3 scripts/okf.py init-bundle .scratch/<id> --id <id> --description "..."
python3 scripts/okf.py stamp <file> --type <okf_type> --stage <stage> --by <producer> \
    [--name ...] [--description ...] [--status draft|stable|deprecated] \
    [--source rel/path.md ...] [--stage-pair key=value ...] [--verified-by ...] [--bundle-dir ...]
python3 scripts/okf.py validate <bundle-or-file> [--require-stages]
```

| Function | Lines | Purpose |
| :--- | :--- | :--- |
| `extract_frontmatter` | 60–98 | Parse YAML frontmatter, using PyYAML when available and a minimal parser otherwise |
| `render_markdown` | 101–108 | Serialise frontmatter and body |
| `append_log` | 111–121 | Append an audit row to `log.md` |
| `refresh_index` | 124–160 | Rebuild the artifact table in `index.md` |
| `init_bundle` | 163–167 | Create `index.md` and `log.md` |
| `stamp_file` | 170–256 | Write deterministic OKF frontmatter |
| `validate_file` | 259–351 | Check one entity file |
| `validate_bundle` | 354–423 | Check every file in a bundle |
| `main` | 426–482 | argparse CLI |

### `scripts/rehydrate.py`

```bash
python3 scripts/rehydrate.py [--workspace <dir> ...]
```

| Function | Lines | Purpose |
| :--- | :--- | :--- |
| `parse_frontmatter` | 25–48 | Lightweight frontmatter reader |
| `find_active_bundles` | 51–85 | Glob `.scratch/*/index.md` in each workspace |
| `rehydrate_workspace` | 88–112 | Build the `injectSteps` system message |
| `main` | 115–144 | CLI and hook entry point |

### `scripts/git_guardrails.py`

```bash
echo '{"command": "git status"}' | python3 scripts/git_guardrails.py
```

| Function | Lines | Purpose |
| :--- | :--- | :--- |
| `extract_command` | 23–42 | Pull the command string out of the hook payload |
| `evaluate_command` | 45–96 | Apply the four deny rules per segment |
| `main` | 99–120 | Read stdin and print the JSON decision |

### `scripts/retro.py`

```bash
python3 scripts/retro.py --transcript <path/to/transcript.jsonl> --bundle-dir <dir> [--output 08_RETRO.md] [--json]
```

| Function | Lines | Purpose |
| :--- | :--- | :--- |
| `extract_tool_names` | 33–56 | Read tool names from a transcript step |
| `analyze_transcript` | 59–135 | Compute steps, tool counts, errors, retry streaks and token estimate |
| `generate_retro_markdown` | 138–182 | Render the report |
| `write_retro_report` | 185–216 | Write and stamp `08_RETRO.md` |
| `main` | 219–241 | CLI |

### Legacy scripts

`scripts/okf_stamp.py` and `scripts/validate_okf.py` predate `okf.py` and duplicate parts of it (`okf_stamp.py` requires PyYAML). New callers should use `okf.py`.

---

## 9. Known gaps

These issues were found while building the docs. The explorer lists them under **Internals → Known gaps**.

1. **Stamping `index.md` overwrites the bundle id.** The triage skill runs `okf.py stamp .scratch/<id>/index.md`. `stamp_file` always sets `id` to the file stem, so the bundle id becomes `index` and rehydration reports bundle `index`.
2. **The bundle `stage` never advances.** `refresh_index` keeps the existing `stage`. Only an explicit stamp of `index.md` changes it, and that triggers gap 1.
3. **`1_assess` is undefined.** It is referenced by `origins.legacy` and `0_triage.next` but has no entry in `stages:`.
4. **Hook path assumptions.** `hooks.json` calls plugin-relative `./scripts/...` but validates workspace-relative `.scratch`. PostToolUse is advisory only (`2>/dev/null || true`).
5. **Dangling agent references.** `@review-arbiter` mentions `@architect` and `@auditor`, which no plugin defines.
6. **Duplicated scripts.** `okf.py`, `git_guardrails.py` and `rehydrate.py` have byte-identical copies in bean-brewer, so they can drift apart. `rules/AGENTS.md` cites `scripts/plan_lint.py`, which lives in bean-brewer.
7. **Hard-coded test path (fixed).** `tests/test_okf.py` used to point at a machine-specific scratch directory. It now uses the repository root.
