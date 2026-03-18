# buildplan.md
## Codex-first adaptation plan for `github.com/uditgoenka/autoresearch`

### Intent

Turn the current Claude-oriented promptware repository into a **Codex-native autonomous improvement system** without throwing away what already works. The implementation should preserve the repo’s strongest ideas:

- one focused change per iteration
- mechanical verification
- git-backed experimentation
- reversible keep/discard decisions
- cumulative learning from prior attempts

The migration should **not** be a shallow rename. It should leave the repo in a shape that a Codex user can actually run, extend, debug, and trust.

---

## 1. Current-state findings

### 1.1 What is solid and worth preserving

1. **The core autoresearch loop is good.**  
   The modify → verify → keep/discard → repeat loop is clear, disciplined, and portable. The baseline/iteration model, bounded vs unbounded runs, and “one change per iteration” rule should remain the center of the system.

2. **Verification and guard are separated.**  
   The distinction between the optimization metric (`Verify`) and a broader safety net (`Guard`) is a real strength. Keep it.

3. **Git is used as experiment memory.**  
   The repo’s insistence on committing experiments before verification and preferring `git revert` over history erasure is conceptually strong.

4. **Workflow specialization is useful.**  
   The plan/debug/fix/security/ship workflows are not random extras. They map to recurring operator needs and should be retained, though re-expressed in a Codex-native form.

5. **References are already modular.**  
   The repo already separates the main skill file from workflow references. That structure can be reused when moving to Codex skills.

### 1.2 What is brittle

1. **The repo is promptware only.**  
   There is almost no mechanical validation of the prompt/document system itself. Behavior is mostly tested manually.

2. **Run state is under-specified.**  
   `autoresearch-results.tsv` is useful, but a single flat log in the working directory is too thin for long-running autonomous work.

3. **The setup flow is over-dependent on interactive gating.**  
   The current model assumes a specific question tool and a particular style of guided wizarding. This is fragile outside Claude.

4. **Release management is duplication-heavy.**  
   The release process syncs hidden `.claude/` sources into root distribution folders and requires manual doc review. That is workable for a small repo, but it is not a durable architecture.

5. **Documentation is too duplicated.**  
   README, guide files, command docs, release notes, and contribution docs all repeat overlapping ideas.

### 1.3 What is tightly coupled to Claude

| Area | Current shape | Why it is Claude-specific |
|---|---|---|
| Install/distribution | `.claude-plugin/`, marketplace manifests, plugin install flow | Anthropic plugin packaging |
| Runtime structure | `.claude/`, `commands/`, `skills/` | Claude Code’s slash-command + skill discovery model |
| Command entrypoints | `/autoresearch`, `/autoresearch:plan`, etc. | Repo-shared slash-command wrappers are Claude-specific here |
| Interactive setup | `AskUserQuestion`, `ToolSearch` references | Assumes Claude-specific tool availability and schema discovery |
| CI examples | `claude -p ...`, `@anthropic-ai/claude-code` install | Anthropic CLI/runtime assumptions |
| Release source-of-truth | hidden `.claude/` tree synced into root | Release pipeline designed around Claude distribution |

### 1.4 What can be reused with adaptation

Keep, but rewrite for Codex tone/assumptions:

- `skills/autoresearch/references/core-principles.md`
- `skills/autoresearch/references/autonomous-loop-protocol.md`
- `skills/autoresearch/references/results-logging.md`
- conceptual content from:
  - `debug-workflow.md`
  - `fix-workflow.md`
  - `security-workflow.md`
  - `ship-workflow.md`
  - `scenario-workflow.md`
  - `predict-workflow.md`

### 1.5 What needs redesign

- command/entrypoint model
- project guidance model
- user setup and onboarding
- run/log directory structure
- rollback strategy in dirty worktrees
- contribution/release structure
- documentation layout
- optional persistent config
- safety and approval boundaries
- Codex-native extensions such as skills, subagents, and project config

---

## 2. Target adaptation strategy

### 2.1 Primary decision

Make the repo **Codex-first** and treat Claude assets as **legacy compatibility material**, not as the architectural center.

### 2.2 Migration strategy

Use a **parallel Codex-native runtime surface**, then progressively retire or isolate Claude-specific assets.

#### Keep as primary concepts
- autoresearch loop
- bounded/unbounded iteration
- single-change discipline
- verify/guard split
- git-backed experiment memory
- workflow specialization

#### Replace as primary mechanisms
- Claude slash-command wrappers
- `AskUserQuestion`-gated control flow
- hidden `.claude/` source-of-truth tree
- flat working-directory result log as the only persistent state
- destructive rollback fallback patterns

### 2.3 Codex-native structure to introduce

```text
AGENTS.md
.codex/
  config.toml
  agents/                # optional; for predict/security reviewer subagents later
.agents/
  skills/
    autoresearch-loop/
      SKILL.md
      references/
      scripts/
    autoresearch-plan/
      SKILL.md
      references/
    autoresearch-debug/
    autoresearch-fix/
    autoresearch-security/
    autoresearch-ship/
    autoresearch-scenario/   # phase 2/3
    autoresearch-predict/    # phase 2/3; likely subagent-backed
.autoresearch/
  targets/
    default.yaml
  runs/
    <timestamp>-<slug>/
      target.yaml
      baseline.json
      results.tsv
      summary.md
      artifacts/
docs/
  index.md
  getting-started.md
  workflows/
  migration/
legacy/
  claude/
    .claude-plugin/
    .claude/
    commands/
    skills/
scripts/
  validate-codex-assets.py
  release.sh
  smoke/
```

### 2.4 Design principles

1. **Codex expectations should feel native.**  
   `AGENTS.md` + `.agents/skills` + `.codex/config.toml` should be the first-class workflow.

2. **Inline prompts stay supported, but persistent config becomes possible.**  
   The current inline fields are useful, but repeated runs should not require retyping Goal/Scope/Metric/Verify every time.

3. **Non-destructive git behavior is mandatory.**  
   The system should assume dirty worktrees are possible and isolate experiments safely.

4. **The repo should become mechanically checkable.**  
   Add validation scripts and smoke fixtures so changes to promptware are not “tested by vibes.”

5. **Secondary workflows should not block a usable v2.**  
   The loop + plan + debug/fix/security/ship path is the minimum viable Codex system. `scenario` and `predict` can follow immediately after if needed.

---

## 3. Exact file and component plan

## 3.1 Existing files to keep, rewrite, or relocate

| Current path | Action | Target path | Notes |
|---|---|---|---|
| `README.md` | Rewrite | `README.md` | Codex-first product positioning and quick start |
| `CONTRIBUTING.md` | Rewrite | `CONTRIBUTING.md` | Contribution flow must describe AGENTS/skills, not Claude install |
| `.claude-plugin/plugin.json` | Relocate or drop | `legacy/claude/.claude-plugin/plugin.json` | Keep only if backward compatibility remains |
| `.claude-plugin/marketplace.json` | Relocate or drop | `legacy/claude/.claude-plugin/marketplace.json` | Legacy only |
| `.claude/` | Relocate | `legacy/claude/.claude/` | No longer source of truth |
| `commands/` | Relocate or delete | `legacy/claude/commands/` | Codex should not depend on repo-shared slash commands |
| `skills/autoresearch/SKILL.md` | Split and rewrite | `AGENTS.md` + `.agents/skills/autoresearch-loop/SKILL.md` + `.agents/skills/autoresearch-plan/SKILL.md` | Main Claude-centric entrypoint becomes Codex guidance + skills |
| `skills/autoresearch/references/autonomous-loop-protocol.md` | Rewrite | `.agents/skills/autoresearch-loop/references/loop-protocol.md` | Keep concepts, remove Claude assumptions |
| `skills/autoresearch/references/core-principles.md` | Rewrite lightly | `.agents/skills/autoresearch-loop/references/core-principles.md` | Mostly portable |
| `skills/autoresearch/references/results-logging.md` | Rewrite | `.agents/skills/autoresearch-loop/references/results-logging.md` | Expand to structured run directory |
| `skills/autoresearch/references/debug-workflow.md` | Rewrite | `.agents/skills/autoresearch-debug/references/debug-workflow.md` | Remove AskUserQuestion dependence |
| `skills/autoresearch/references/fix-workflow.md` | Rewrite | `.agents/skills/autoresearch-fix/references/fix-workflow.md` | Same |
| `skills/autoresearch/references/security-workflow.md` | Rewrite heavily | `.agents/skills/autoresearch-security/references/security-workflow.md` | Replace Claude CLI and Anthropic CI assumptions |
| `skills/autoresearch/references/ship-workflow.md` | Rewrite | `.agents/skills/autoresearch-ship/references/ship-workflow.md` | Add Codex-safe confirmation boundaries |
| `skills/autoresearch/references/scenario-workflow.md` | Rewrite later | `.agents/skills/autoresearch-scenario/references/...` | second-wave migration |
| `skills/autoresearch/references/predict-workflow.md` | Redesign | `.agents/skills/autoresearch-predict/...` + optional `.codex/agents/*.toml` | should become subagent-backed rather than purely simulated personas |
| `guide/` | Consolidate | `docs/` | reduce duplication |
| `scripts/release.sh` | Rewrite | `scripts/release.sh` | release root Codex assets; optionally package legacy Claude bundle |
| `scripts/release.md` | Rewrite | `docs/maintainers/release.md` | new release source of truth |
| `context7.json` | Keep unless unused | `context7.json` | not Claude-specific by itself |

## 3.2 New files to add

| New path | Purpose |
|---|---|
| `AGENTS.md` | durable repo-wide Codex guidance |
| `.codex/config.toml` | project-scoped Codex defaults |
| `codex/rules/safety.rules` | optional prompt/block rules for high-risk commands |
| `.agents/skills/autoresearch-loop/SKILL.md` | primary autonomous improvement workflow |
| `.agents/skills/autoresearch-plan/SKILL.md` | goal-to-config skill |
| `.agents/skills/autoresearch-debug/SKILL.md` | bug hunting workflow |
| `.agents/skills/autoresearch-fix/SKILL.md` | error reduction workflow |
| `.agents/skills/autoresearch-security/SKILL.md` | read-first security workflow |
| `.agents/skills/autoresearch-ship/SKILL.md` | release/readiness workflow |
| `.autoresearch/targets/default.yaml` | persistent target config example |
| `scripts/validate-codex-assets.py` | lint skill metadata, file paths, legacy refs |
| `scripts/smoke/*.sh` or `*.py` | reproducible smoke tests against fixtures |
| `test-fixtures/` | deterministic repositories for skill smoke tests |
| `docs/getting-started.md` | codex-first onboarding |
| `docs/migration/from-claude.md` | explain major-version migration and legacy location |

---

## 4. Migration phases

## Phase 0 — Baseline audit and acceptance criteria

### Tasks
- inventory all Claude-only files, strings, and assumptions
- define target repo tree
- write architecture and operating doctrine docs
- define release scope: full v2 vs staged alpha
- identify which workflows are required for v2 GA vs post-v2 follow-up

### Deliverables
- `buildplan.md`
- `architecture.md`
- `agents.md`
- `checklist.md`

### Exit criteria
- a maintainer can answer “what stays, what goes, what moves, what ships first” from the docs alone

---

## Phase 1 — Codex runtime scaffold

### Tasks
1. Add root `AGENTS.md`
2. Add `.codex/config.toml`
3. Add `.agents/skills/` skeletons for:
   - `autoresearch-loop`
   - `autoresearch-plan`
   - `autoresearch-debug`
   - `autoresearch-fix`
   - `autoresearch-security`
   - `autoresearch-ship`
4. Add `codex/rules/safety.rules` as an optional starter
5. Add `.autoresearch/targets/` and `.autoresearch/runs/` conventions
6. Update `.gitignore` to ignore `.autoresearch/runs/`

### What to keep vs replace
- Keep current reference content as source material
- Replace Claude-centric discovery and setup assumptions

### Exit criteria
- Codex can discover project guidance and repo skills
- a contributor can see the intended Codex runtime surface without touching legacy files

---

## Phase 2 — Core loop migration

### Tasks
1. Rewrite the loop instructions into a Codex skill
2. Replace inline-only configuration with:
   - accepted inline fields for fast use
   - optional persistent target file under `.autoresearch/targets/*.yaml`
3. Define the new preflight:
   - inspect repo status
   - detect dirty worktree
   - choose in-place branch vs detached worktree
   - establish baseline
4. Define structured run logging under `.autoresearch/runs/<run-id>/`
5. Rewrite rollback policy:
   - prefer dedicated branch/worktree
   - use `git revert` for discarded iteration commits
   - do **not** use destructive reset fallback
6. Add stagnation policy
   - after N inconclusive/discarded attempts, force reflection
   - after hard threshold, stop with summary unless the user explicitly wants persistence

### Exit criteria
- there is a usable `$autoresearch-loop`
- it can execute against a target config
- run state is durable and inspectable
- rollback works safely in dirty-repo scenarios

---

## Phase 3 — Planning skill migration

### Tasks
1. Rewrite `/autoresearch:plan` as `$autoresearch-plan`
2. Convert current wizard logic into:
   - infer-from-repo first
   - ask only for missing information
   - produce a validated target file
3. Define validation checks:
   - scope resolves
   - verify command exists and returns output
   - metric extraction strategy is defined
   - direction is explicit
   - guard is optional but valid if present
4. Generate both:
   - machine-readable target file
   - human-readable summary for review

### Exit criteria
- `$autoresearch-plan` creates reusable target configs
- `$autoresearch-loop` can consume the output without translation

---

## Phase 4 — Workflow migration (debug / fix / security / ship)

### Tasks
#### Debug
- remove `AskUserQuestion` hard requirement
- keep hypothesis-driven loop
- add structured finding objects and evidence fields

#### Fix
- keep “one fix per iteration”
- add hard rule: error count must decrease or change is discarded
- support `--from-debug` by reading structured findings from latest run directory

#### Security
- keep read-first posture by default
- replace Anthropic CLI examples with Codex-compatible CI guidance
- isolate auto-remediation behind explicit opt-in
- add severity gating that is tool/runtime-neutral

#### Ship
- keep multi-phase readiness model
- split “prepare” vs “execute” more clearly
- require explicit approval for state-changing actions such as push, publish, deploy, merge, send

### Exit criteria
- four primary auxiliary workflows are Codex-usable
- no non-legacy file references `.claude/`, `AskUserQuestion`, `ToolSearch`, or `claude -p`

---

## Phase 5 — Secondary workflow redesign (scenario / predict)

### Tasks
#### Scenario
- preserve scenario exploration utility
- reframe as optional idea-generation / edge-case exploration skill
- remove heavy interactive setup dependence

#### Predict
- redesign to use Codex subagents or custom agents where beneficial
- map current personas into explicit narrow roles:
  - architect
  - security reviewer
  - performance reviewer
  - reliability reviewer
  - skeptic/devil’s advocate
- keep a single consolidated output format

### Exit criteria
- either both skills are migrated cleanly
- or they are explicitly marked “post-v2” and isolated from the GA surface

---

## Phase 6 — Documentation consolidation

### Tasks
1. Rewrite `README.md` as a Codex-first entrypoint
2. Collapse duplicated guide material into `docs/`
3. Add:
   - getting started
   - architecture overview
   - workflow docs
   - migration from Claude
   - troubleshooting
4. Rewrite `CONTRIBUTING.md`
5. Rewrite release docs
6. Mark any legacy Claude docs clearly as legacy

### Exit criteria
- a new user can set up and run the system without knowing anything about Claude
- a contributor can extend a skill without guessing where the source of truth lives

---

## Phase 7 — Validation and release hardening

### Tasks
1. Add repository validation scripts
2. Add smoke tests against fixtures
3. Dry-run the release flow
4. Verify docs links and skill metadata
5. Validate that legacy Claude compatibility, if retained, is intentionally isolated and labeled
6. Cut a major version release (`v2.0.0` recommended)

### Exit criteria
- maintainers can release without manual sync confusion
- Codex-first assets are the source of truth
- release notes clearly describe the migration

---

## 5. Codex-compatibility workstreams

### 5.1 Instruction layer
- add root `AGENTS.md`
- move durable repository rules out of skill bodies
- keep skill docs focused on workflow logic

### 5.2 Skill layer
- replace repo-shared slash-command wrappers with `.agents/skills`
- make descriptions narrow and discoverable
- support explicit invocation by skill name

### 5.3 Configuration layer
- add `.codex/config.toml`
- introduce persistent autoresearch target config
- define run directory conventions

### 5.4 Git/safety layer
- eliminate destructive reset fallback
- prefer worktree or branch isolation
- define confirmation boundaries for push/publish/deploy

### 5.5 Review/validation layer
- add mechanical validation of skill metadata and legacy references
- add smoke fixtures for representative workflows

### 5.6 Optional advanced layer
- subagents for `predict`
- MCP-backed metrics only when local verification is insufficient
- execpolicy rules for dangerous commands

---

## 6. Documentation workstreams

### Workstream A — Product and onboarding
Files:
- `README.md`
- `docs/getting-started.md`
- `docs/migration/from-claude.md`

### Workstream B — Contributor docs
Files:
- `CONTRIBUTING.md`
- `AGENTS.md`
- `docs/maintainers/release.md`

### Workstream C — Workflow docs
Files:
- `docs/workflows/loop.md`
- `docs/workflows/plan.md`
- `docs/workflows/debug.md`
- `docs/workflows/fix.md`
- `docs/workflows/security.md`
- `docs/workflows/ship.md`

### Workstream D — Legacy docs
Files:
- `legacy/claude/README.md`
- legacy pointers from old install docs

---

## 7. Command/skill restructuring workstreams

## 7.1 Replace command wrappers with skills

Current model:
- root command files parse flags and point to `.claude/skills/...`

Target model:
- each workflow is a self-contained Codex skill directory

### Why
- Codex reusable prompts are skill-oriented, not repo-shared slash-command oriented
- workflow files become easier to version and validate

### Tradeoff
- users lose the exact `/autoresearch:foo` syntax as the primary interface
- gain: discoverable repo-native skills and a structure Codex expects

## 7.2 Split durable rules from workflow steps

Move into `AGENTS.md`:
- git safety rules
- commit hygiene
- one-change-per-iteration discipline
- verification requirements
- logging and rollback expectations

Keep inside individual skills:
- task-specific workflow steps
- task-specific outputs
- task-specific flags/options

### Why
The current repo repeats durable behavior across command docs and references.

### Tradeoff
Slightly more up-front design work, much lower long-term drift.

---

## 8. Testing and validation steps

## 8.1 Static validation
- assert every skill directory has a `SKILL.md`
- assert every skill has `name` and `description`
- assert references linked from skill docs exist
- assert non-legacy files contain no:
  - `.claude/`
  - `AskUserQuestion`
  - `ToolSearch`
  - `claude -p`
  - `@anthropic-ai/claude-code`
- assert docs do not describe Claude as the primary runtime

## 8.2 Smoke validation
Against small fixture repos:
- `$autoresearch-plan` creates a target file
- `$autoresearch-loop` establishes baseline and logs run state
- discard path works when metric regresses
- guard failure discards change
- dirty worktree path chooses safe isolation
- `$autoresearch-debug` produces structured findings
- `$autoresearch-fix` reduces error count
- `$autoresearch-security` runs read-only and emits report
- `$autoresearch-ship --checklist-only` produces readiness output

## 8.3 UX validation
- first-time user path from README works
- skill discovery is obvious
- target config format is understandable
- troubleshooting points to actual fixes, not generic advice

## 8.4 Release validation
- release script updates Codex-first assets
- version references are not duplicated across multiple incompatible sources of truth
- legacy bundle, if shipped, is clearly marked and versioned intentionally

---

## 9. Rollout sequence

### Recommended sequence

1. **Write the planning docs**  
   This step is complete with the files in this adaptation package.

2. **Land Codex scaffold in a feature branch**  
   Add `AGENTS.md`, `.codex/`, `.agents/skills/`, `.autoresearch/`, and validation scripts.

3. **Port the core loop and planning skill first**  
   These determine whether the repo is meaningfully Codex-compatible.

4. **Port debug/fix/security/ship**  
   These complete the useful core.

5. **Consolidate docs and contribution flow**  
   Make the Codex path the default public story.

6. **Decide fate of scenario/predict**  
   Either finish them for v2 or clearly defer them.

7. **Cut a breaking release**  
   Recommended version: `v2.0.0`

---

## 10. Risks and mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Over-preserving Claude structure | would produce an awkward, non-native Codex port | make Codex layout primary; isolate legacy |
| Over-rewriting from scratch | loses working protocol knowledge | reuse reference content and loop semantics |
| Dirty worktree conflicts | Codex safety guidance is stricter about unrelated changes | use branch/worktree isolation |
| Too much duplication remains | maintainability will still be poor | consolidate docs and source-of-truth paths |
| No automated validation | regressions in promptware will slip through | add static validator + smoke fixtures |
| Predict/scenario delay | users may expect all 8 workflows immediately | prioritize core, communicate phase 2 clearly |
| Config sprawl | too many files can make setup harder | keep one root `AGENTS.md`, one project config, one target format |
| False Codex assumptions | can make the repo feel broken | stick to official Codex concepts: AGENTS, skills, config, rules, subagents |

---

## 11. Definition of done

The adaptation is done when all of the following are true:

- the repo has a **root `AGENTS.md`**
- the repo has **Codex-discoverable skills under `.agents/skills/`**
- the repo can be used **without any Claude plugin install**
- the **core loop works in Codex** with:
  - baseline
  - one-change iteration
  - verify
  - guard
  - keep/discard
  - structured logging
  - safe rollback
- **README and onboarding are Codex-first**
- **CONTRIBUTING** describes Codex contribution/testing flow
- **release tooling no longer treats hidden `.claude/` assets as the canonical source**
- **non-legacy files no longer rely on `AskUserQuestion`, `ToolSearch`, or `claude -p`**
- the repo has **mechanical validation scripts**
- the repo has **smoke fixtures/tests**
- the repo has a **clear legacy story**:
  - either Claude assets are isolated under `legacy/claude`
  - or they are removed in the major release
- the system feels **intentionally designed for Codex**, not cosmetically renamed

---

## 12. First implementation slice after planning

The highest-leverage first coding slice is:

1. add `AGENTS.md`
2. add `.codex/config.toml`
3. add `.agents/skills/autoresearch-loop/`
4. add `.agents/skills/autoresearch-plan/`
5. add `.autoresearch/targets/default.yaml`
6. add `scripts/validate-codex-assets.py`
7. rewrite `README.md` and `CONTRIBUTING.md` to point at the new Codex surface
8. move Claude assets under `legacy/claude/` or clearly mark them legacy

That slice gives the repo a real Codex spine instead of a renamed Claude shell.
