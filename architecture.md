# architecture.md
## Current architecture and target Codex architecture for `autoresearch`

---

## 1. Executive summary

`autoresearch` today is a **Claude-first, Markdown-driven workflow repository**. It does not contain an executable loop engine in code; instead, it packages behavior as:

- command registration markdown
- a single main skill entrypoint
- detailed workflow reference markdown
- guide docs
- release sync scripts

That design is portable in spirit, but not in runtime shape. The biggest architectural problem is not “Claude branding.” It is that the repo’s **primary operating model is built around Claude’s plugin + slash-command + question-tool assumptions**.

The target architecture should therefore be:

- **Codex-first at the root**
- **skill-centric instead of command-wrapper-centric**
- **explicit about config, run state, safety, and logs**
- **non-destructive in dirty repositories**
- **maintainable by humans and future agents**

---

## 2. Repository structure as found today

```text
.
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .claude/
│   ├── commands/
│   └── skills/autoresearch/
├── commands/
│   ├── autoresearch.md
│   └── autoresearch/
│       ├── debug.md
│       ├── fix.md
│       ├── plan.md
│       ├── predict.md
│       ├── scenario.md
│       ├── security.md
│       └── ship.md
├── guide/
│   ├── README.md
│   ├── getting-started.md
│   ├── autoresearch.md
│   ├── autoresearch-plan.md
│   ├── autoresearch-debug.md
│   ├── autoresearch-fix.md
│   ├── autoresearch-security.md
│   ├── autoresearch-ship.md
│   ├── autoresearch-scenario.md
│   ├── autoresearch-predict.md
│   ├── advanced-patterns.md
│   ├── chains-and-combinations.md
│   └── examples-by-domain.md
├── skills/
│   └── autoresearch/
│       ├── SKILL.md
│       └── references/
│           ├── autonomous-loop-protocol.md
│           ├── core-principles.md
│           ├── debug-workflow.md
│           ├── fix-workflow.md
│           ├── plan-workflow.md
│           ├── predict-workflow.md
│           ├── results-logging.md
│           ├── scenario-workflow.md
│           ├── security-workflow.md
│           └── ship-workflow.md
├── scripts/
│   ├── release.md
│   └── release.sh
├── CONTRIBUTING.md
├── README.md
└── context7.json
```

### Architectural observation

The repo actually contains **two overlapping distribution layers**:

1. hidden `.claude/` content
2. root `commands/` + `skills/` content

The release process syncs from the hidden layer into the root distribution layer. That is already a sign that the runtime/distribution architecture is fighting itself.

---

## 3. Current architecture: control flow

## 3.1 Current entrypoints

The user enters one of these Claude-style commands:

- `/autoresearch`
- `/autoresearch:plan`
- `/autoresearch:debug`
- `/autoresearch:fix`
- `/autoresearch:security`
- `/autoresearch:ship`
- `/autoresearch:scenario`
- `/autoresearch:predict`

## 3.2 Current command model

Each command markdown file is a thin wrapper that:

1. parses arguments
2. points to a workflow reference file under `.claude/skills/autoresearch/references/...`
3. instructs Claude to execute immediately
4. often requires `AskUserQuestion` if key arguments are missing

This means the command files are not true workflow owners. They are dispatch stubs.

## 3.3 Current main skill model

`skills/autoresearch/SKILL.md` functions as a global router and doctrine file. It:

- describes the overall skill
- defines a mandatory interactive setup gate
- refers out to specific workflow references
- frames the loop philosophy

This makes `SKILL.md` simultaneously:

- user-facing explanation
- runtime doctrine
- workflow router
- activation table

That is too much responsibility for one file.

## 3.4 Current loop control flow

Current abstract flow:

```text
User invokes command
  -> command wrapper parses inline flags
  -> main skill / workflow reference is loaded
  -> interactive gate runs (often mandatory)
  -> setup establishes goal / scope / metric / verify / guard
  -> baseline run
  -> iteration loop:
       read current state and prior results
       choose one change
       modify files
       commit experiment
       run verify
       run guard (optional)
       keep or revert
       log result
       continue
```

This general flow is good and should survive.

---

## 4. Current configuration model

### What exists now
The current system relies almost entirely on **inline prompt fields and flags**:

- `Goal:`
- `Scope:`
- `Metric:`
- `Verify:`
- `Guard:`
- `Iterations:`
- command-specific flags such as `--fix`, `--fail-on`, `--type`, etc.

### What is missing
There is no true project-scoped persistent runtime configuration for autoresearch itself.

### Consequences
- repeated runs require repeated setup
- run reproducibility is lower than it should be
- CI reuse is awkward
- planning output is less durable than it should be

---

## 5. Current logging/results model

### What exists now
A TSV log:

```text
autoresearch-results.tsv
```

Columns currently described:

- iteration
- commit
- metric
- delta
- guard
- status
- description

### Strengths
- simple
- append-friendly
- easy to inspect by humans and scripts

### Weaknesses
- no per-run isolation
- no saved baseline command output
- no structured config snapshot
- no obvious place for artifacts, evidence, or debug/security findings
- difficult to resume safely after interruption

---

## 6. Current verification model

### Strengths
- mechanical verification is mandatory
- baseline iteration exists
- metric direction is explicit in the planning workflow
- optional guard lets the system reject “improvements” that break broader correctness

### Weaknesses
- verification instructions are mostly textual, not strongly normalized
- output parsing strategy is not first-class
- ambiguous verification handling is underspecified
- there is no standard machine-readable target file

---

## 7. Current rollback model

### Current intent
- commit before verify
- keep if better
- `git revert` if worse
- preserve experimental history

### Strength
This is philosophically correct. Failed experiments are still useful information.

### Weakness
The current protocol also allows a destructive fallback path. That is a poor fit for Codex’s git-safety posture and for real developer environments with unrelated local changes.

---

## 8. Current command/skill model

### Current model
- command wrappers in `commands/`
- main skill in `skills/autoresearch/`
- detailed references in `skills/autoresearch/references/`
- guide docs in `guide/`

### Problems
1. command wrappers are the public entrypoint, but not the true source of workflow logic
2. `SKILL.md` holds too many concerns
3. repo-shared command registration is not Codex’s preferred reusable workflow mechanism
4. documentation and runtime instructions drift easily

---

## 9. Current user interaction and setup model

### Current user flow
1. install via Claude plugin or copy into `.claude/...`
2. invoke slash command
3. answer batched questions if arguments are incomplete
4. Claude executes the workflow

### Problems
- onboarding is Claude-only
- interaction assumes a specific question tool
- non-interactive or CI use cases are entangled with interactive setup patterns
- setup output is not a durable artifact by default

---

## 10. Current failure modes

| Failure mode | Current weakness |
|---|---|
| dirty worktree | protocol assumes more cleanliness/control than Codex should |
| missing question tool | workflow may stall due to `AskUserQuestion` dependency |
| verify command ambiguous | no strong standardized parser/result contract |
| repeated failed ideas | logs exist, but reflection/stagnation policy is weak |
| docs drift | many duplicated docs and two source trees |
| release drift | hidden `.claude/` source-of-truth plus root distribution sync |
| secondary workflows | `predict` and `scenario` are instruction-heavy and interactive-tool-heavy |

---

## 11. Current problems (architectural diagnosis)

### Problem 1 — Runtime model mismatch
The repo is built around Claude command registration and a Claude-specific interactive tool, while Codex’s reusable customization surface is centered on `AGENTS.md`, skills, config layers, and optional subagents.

### Problem 2 — Too much logic in prose without supporting structure
The repo’s operating model is encoded in large markdown files, but the repo does not add enough surrounding structure (persistent config, run directories, validation tooling) to make that reliable over time.

### Problem 3 — Unsafe rollback assumptions for Codex
The current loop philosophy is strong, but the git safety model is not aligned with a Codex environment that may begin inside a dirty repo and should not revert unrelated work.

### Problem 4 — Hidden source-of-truth confusion
`.claude/` and root distribution directories create cognitive overhead and release complexity.

### Problem 5 — Weak separation of permanent guidance vs workflow logic
Durable rules such as git hygiene, logging rules, and safety boundaries are mixed into workflow files that should focus on task-specific behavior.

### Problem 6 — Documentation is a maintenance burden
The docs are rich, but too duplicated to remain trustworthy without discipline.

---

## 12. Target architecture

## 12.1 Target repository structure

```text
.
├── AGENTS.md
├── .codex/
│   ├── config.toml
│   └── agents/                 # optional; phase 2+ for predict/review
├── .agents/
│   └── skills/
│       ├── autoresearch-loop/
│       │   ├── SKILL.md
│       │   ├── references/
│       │   └── scripts/
│       ├── autoresearch-plan/
│       ├── autoresearch-debug/
│       ├── autoresearch-fix/
│       ├── autoresearch-security/
│       ├── autoresearch-ship/
│       ├── autoresearch-scenario/
│       └── autoresearch-predict/
├── .autoresearch/
│   ├── targets/
│   │   └── default.yaml
│   └── runs/
│       └── <run-id>/
│           ├── target.yaml
│           ├── baseline.json
│           ├── results.tsv
│           ├── summary.md
│           └── artifacts/
├── docs/
│   ├── index.md
│   ├── getting-started.md
│   ├── workflows/
│   ├── maintainers/
│   └── migration/
├── scripts/
│   ├── validate-codex-assets.py
│   ├── smoke/
│   └── release.sh
├── legacy/
│   └── claude/                 # optional compatibility quarantine
├── README.md
└── CONTRIBUTING.md
```

---

## 13. Target control flow

## 13.1 Core loop flow

```text
User prompt or explicit skill invocation
  -> AGENTS.md loads automatically
  -> chosen skill loads on demand
  -> input source:
       inline prompt fields
       OR persistent target file
  -> preflight:
       inspect repo + git state
       determine safe work area
       verify tool/command availability
       establish baseline
  -> run directory created
  -> iteration loop:
       read prior experiments / logs / git history
       choose one hypothesis
       make one focused change
       commit experiment on run branch
       run verify
       run guard if configured
       keep or discard
       log iteration outcome
       reflect if stagnating
  -> stop:
       goal reached OR iteration cap OR hard block OR user interrupt
  -> emit summary + best state + next-step recommendations
```

## 13.2 Planning flow

```text
User asks for help setting up a target
  -> plan skill inspects repo and any user prompt
  -> infer as much as possible
  -> ask only for missing required pieces
  -> validate scope / verify / metric direction
  -> write target config file
  -> produce copyable summary
```

---

## 14. Target configuration model

### 14.1 Layers

1. `AGENTS.md`  
   Durable repository behavior and operator doctrine

2. `.codex/config.toml`  
   Codex project defaults (model, sandbox/approval posture, optional agent settings)

3. `.autoresearch/targets/*.yaml`  
   Reusable run targets describing:
   - goal
   - scope
   - metric
   - direction
   - verify command
   - guard command
   - stop conditions

4. inline prompt overrides  
   Useful for one-off runs without mutating target files

### 14.2 Proposed target file shape

Example:

```yaml
name: default
goal: Increase test coverage in the API layer
scope:
  include:
    - src/api/**/*.ts
    - tests/api/**/*.ts
metric:
  name: coverage_percent
  direction: higher
  extractor: coverage-summary
verify:
  command: npm test -- --coverage
guard:
  command: npm run lint && npm run typecheck
stopping:
  max_iterations: 20
  goal_threshold: 90
  stagnation_reflect_after: 5
  stop_after_consecutive_failures: 10
```

### Why this shape
- captures the repo’s existing mental model
- keeps the valuable verify/guard split
- is durable and reviewable
- gives Codex a reusable artifact instead of ephemeral inline setup only

### Tradeoff
Adds a file format and slightly more structure. The gain in repeatability is worth it.

---

## 15. Target logging/results model

## 15.1 Proposed run directory

```text
.autoresearch/runs/2026-03-18T150500Z-coverage/
  target.yaml
  baseline.json
  results.tsv
  summary.md
  artifacts/
```

## 15.2 Proposed files

### `target.yaml`
Snapshot of the exact run target after resolving overrides.

### `baseline.json`
Stores:
- verify command
- guard command
- parsed baseline metric
- raw relevant command output summary
- repo commit/branch metadata at run start

### `results.tsv`
Suggested columns:

- iteration
- timestamp
- branch
- commit
- metric
- best_metric
- delta_from_best
- verify_status
- guard_status
- decision
- hypothesis
- files_touched
- artifact_path

### `summary.md`
Human summary of:
- goal
- baseline
- best result
- kept experiments
- discarded experiments
- blockers
- next likely moves

## 15.3 Benefits
- restartability
- per-run auditability
- better experiment memory
- room for debug/security/ship artifacts
- easier future automation

---

## 16. Target verification model

### Rules
1. baseline must be measured before iteration 1
2. each iteration must run the declared verify path
3. guard must pass for a change to be kept if guard is configured
4. metric parsing must be explicit
5. ambiguous verify output is an error state, not a silent keep

### Improvement
Planning should produce a known parsing method or extraction contract, not just a natural-language metric description.

### Optional extension
Support helper scripts for parsing metrics where the verify command alone is too noisy.

---

## 17. Target rollback model

## 17.1 Policy
- never assume a clean repo
- do not revert unrelated user changes
- prefer dedicated run branch
- prefer dedicated worktree when the starting worktree is dirty or risky
- discard failed experiments with `git revert`
- do not use destructive hard reset as a normal control path

## 17.2 Recommended flow
1. inspect `git status`
2. if unrelated local changes exist:
   - create a run worktree off current HEAD
3. run experiments there
4. keep successful experiment commits on the run branch
5. merge/cherry-pick accepted results back intentionally
6. remove the worktree when done

### Why
This preserves the spirit of git-as-memory without violating Codex-safe git behavior.

### Tradeoff
More branch/worktree management. Consider it necessary complexity, not accidental complexity.

---

## 18. Target command/skill model

## 18.1 Primary interface
Codex skills under `.agents/skills/`

Suggested skills:
- `autoresearch-loop`
- `autoresearch-plan`
- `autoresearch-debug`
- `autoresearch-fix`
- `autoresearch-security`
- `autoresearch-ship`
- `autoresearch-scenario`
- `autoresearch-predict`

## 18.2 Secondary interface
Inline prompting using Codex best-practice prompt shape:

- Goal
- Context
- Constraints
- Done when

The plan skill converts this into a durable autoresearch target.

## 18.3 Legacy interface
Optional `legacy/claude/` bundle for prior users. It should never remain the architectural source of truth.

---

## 19. Target user interaction/setup model

## First-time user flow

1. open the repository in Codex
2. trust the project so project-scoped config and instructions load
3. read `README.md`
4. run `$autoresearch-plan` or provide a prepared target file
5. review the generated target config
6. run `$autoresearch-loop`
7. inspect `.autoresearch/runs/latest` (or the printed run path) and the git diff/branch

## Why this is better
- explicit
- durable
- reproducible
- aligned with Codex customization surfaces

---

## 20. Codex integration points

| Codex feature | Role in target architecture |
|---|---|
| `AGENTS.md` | repository-wide permanent doctrine |
| `.agents/skills` | reusable workflow packaging |
| `.codex/config.toml` | repo-scoped defaults |
| `codex/rules/*.rules` | high-risk command guardrails |
| subagents/custom agents | optional advanced implementation for `predict`, review, or evidence gathering |
| built-in review flow | optional final review step before accepting risky changes |

---

## 21. Extensibility model

### Adding a new workflow
To add a new workflow in the target design:

1. create a new skill directory
2. write a tight `SKILL.md` with `name` and `description`
3. add workflow references only if needed
4. update docs
5. add static validation coverage
6. add a smoke example or fixture scenario

### Why this is better than the current model
It removes the need to wire:
- command registration
- skill router updates
- duplicated guide changes
- hidden distribution sync

---

## 22. Failure modes in the target architecture

| Failure mode | Target handling |
|---|---|
| verify command missing | planning fails fast; loop does not start |
| metric parse ambiguous | mark run blocked; require target fix |
| dirty worktree | isolate in worktree/branch |
| repeated non-improving iterations | reflection threshold, then controlled stop |
| guard always failing | log blocked run; do not keep changes |
| user asks for destructive action | require explicit approval boundary |
| skill drift | validation script catches broken references and legacy strings |
| docs drift | codex-first docs become single source of truth |

---

## 23. Security and guardrail considerations

### Baseline guardrails
- no destructive git commands by default
- no push/publish/deploy/send/merge without explicit user approval
- security workflow defaults to read-only
- auto-remediation only on explicit opt-in
- external systems or network metrics require explicit setup/approval
- run logs should not capture secrets

### Optional repo rules
Use Codex execpolicy rules to:
- prompt on `git push`
- prompt on `gh pr merge`
- prompt on `npm publish`
- prompt on `kubectl`, `terraform apply`, `fly deploy`, etc.
- forbid `git reset --hard` as a normal path

---

## 24. Target improvements summary

| Current problem | Target improvement |
|---|---|
| Claude slash-command dependence | Codex skills as first-class runtime |
| interactive tool dependence | infer-first, ask-only-when-blocked setup |
| hidden `.claude/` source-of-truth | root Codex assets are canonical |
| flat result log | structured run directories |
| destructive rollback fallback | worktree/branch isolation + revert |
| inline-only config | persistent target files |
| duplicated docs | consolidated `docs/` |
| weak validation | validation script + smoke fixtures |
| simulated personas only | optional real Codex subagents for `predict` |

---

## 25. Architectural decisions and rationale

| Decision | Why needed | Why this shape | Codex benefit | Tradeoff |
|---|---|---|---|---|
| Make Codex assets primary | runtime mismatch is the biggest issue | root `AGENTS.md`, `.agents/skills`, `.codex/` are Codex-native | natural workflow for Codex users | major-version migration |
| Keep legacy Claude assets isolated | avoids breaking all existing users overnight | `legacy/claude/` quarantine | clean primary architecture + optional compatibility | some repo size overhead |
| Add persistent target configs | inline-only setup is brittle | `.autoresearch/targets/*.yaml` mirrors current mental model | repeatable runs and CI reuse | one more file type |
| Add structured run directories | flat TSV is too weak for long runs | per-run directory with config, baseline, log, summary | restartability and observability | modest complexity |
| Use worktree/branch isolation | Codex should not trample dirty repos | explicit safe work area selection | safer autonomous operation | more git mechanics |
| Split doctrine from workflows | current files mix permanent and task-specific rules | `AGENTS.md` for durable rules, skills for workflows | better skill focus and lower drift | requires careful refactor |
| Defer or redesign `predict` with subagents | current persona simulation is not the best Codex-native shape | optional `.codex/agents/*.toml` roles | uses actual Codex strengths | phase 2 complexity |
| Add validation tooling | markdown promptware otherwise regresses silently | lightweight scripts + fixtures | maintainability and release confidence | initial setup cost |

---

## 26. Recommended v2 scope boundary

### Must ship in v2.0.0
- Codex-first root architecture
- `AGENTS.md`
- `autoresearch-loop`
- `autoresearch-plan`
- `autoresearch-debug`
- `autoresearch-fix`
- `autoresearch-security`
- `autoresearch-ship`
- structured run logging
- safe rollback model
- Codex-first docs
- validation scripts

### Can follow in v2.1 if needed
- `autoresearch-scenario`
- `autoresearch-predict` full redesign with subagents
- deeper MCP integrations
- richer fixture suite

This split gets a credible Codex system shipped sooner without pretending the port is done when only the naming changed.
