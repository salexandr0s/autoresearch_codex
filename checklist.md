# checklist.md
## End-to-end checklist for the Codex adaptation of `autoresearch`

Use this as the execution checklist for the migration. Keep it updated as work lands.

---

## 1. Repo audit checklist

- [ ] Inventory all top-level directories and confirm which are runtime-critical vs documentation-only
- [ ] Confirm whether `.claude/` is still treated as source of truth anywhere
- [ ] Confirm every root `commands/` file that exists today
- [ ] Confirm every current workflow reference file under `skills/autoresearch/references/`
- [ ] Confirm every place `README.md` describes Claude-specific setup
- [ ] Confirm every place `CONTRIBUTING.md` describes Claude-specific development flow
- [ ] Confirm every place `scripts/release.*` references `.claude/`, plugin manifests, or manual sync steps
- [ ] Confirm every guide page that duplicates quick start, install, or command descriptions
- [ ] Confirm whether `context7.json` should remain in the v2 repo
- [ ] Record any version/source-of-truth inconsistencies before modifying release logic

---

## 2. Claude-specific dependency removal checklist

### Install/distribution
- [ ] Remove Claude plugin install as the primary onboarding path
- [ ] Decide whether `.claude-plugin/` will be removed or moved to `legacy/claude/`
- [ ] Decide whether `.claude/` will be removed or moved to `legacy/claude/`

### Runtime assumptions
- [ ] Remove `.claude/skills/...` references from non-legacy runtime files
- [ ] Remove `.claude/commands/...` references from non-legacy runtime files
- [ ] Remove `AskUserQuestion` from non-legacy runtime files
- [ ] Remove `ToolSearch` references from non-legacy runtime files
- [ ] Remove `claude -p` examples from non-legacy docs and CI examples
- [ ] Remove `@anthropic-ai/claude-code` install instructions from non-legacy docs
- [ ] Remove “Claude reads this first” assumptions from non-legacy docs

### Public positioning
- [ ] Rewrite project description so it no longer markets the repo as Claude-only
- [ ] Update badges, descriptions, and examples to be Codex-first
- [ ] Add a clear legacy note if Claude compatibility is intentionally retained

---

## 3. Codex compatibility checklist

### Core repository surfaces
- [ ] Add root `AGENTS.md`
- [ ] Add `.codex/config.toml`
- [ ] Add `.agents/skills/`
- [ ] Add `.autoresearch/targets/`
- [ ] Add `.autoresearch/runs/`
- [ ] Add `codex/rules/` if execpolicy rules are adopted

### Skill packaging
- [ ] Create `.agents/skills/autoresearch-loop/SKILL.md`
- [ ] Create `.agents/skills/autoresearch-plan/SKILL.md`
- [ ] Create `.agents/skills/autoresearch-debug/SKILL.md`
- [ ] Create `.agents/skills/autoresearch-fix/SKILL.md`
- [ ] Create `.agents/skills/autoresearch-security/SKILL.md`
- [ ] Create `.agents/skills/autoresearch-ship/SKILL.md`
- [ ] Decide v2 status of `.agents/skills/autoresearch-scenario/`
- [ ] Decide v2 status of `.agents/skills/autoresearch-predict/`

### Skill quality
- [ ] Ensure every skill has `name`
- [ ] Ensure every skill has `description`
- [ ] Ensure descriptions are narrow enough for Codex to choose correctly
- [ ] Ensure each skill’s `SKILL.md` is concise and references longer docs only when needed
- [ ] Ensure durable repository rules are not duplicated across multiple skill files

### Prompt model
- [ ] Support Goal/Context/Constraints/Done-when style prompting in docs/examples
- [ ] Support fast inline overrides without requiring a persistent target file
- [ ] Support a validated persistent target config for repeatable runs

---

## 4. Core loop migration checklist

### Preflight
- [ ] Define repo inspection preflight
- [ ] Define dirty worktree handling
- [ ] Define worktree-or-branch isolation policy
- [ ] Define baseline capture format
- [ ] Define stop conditions

### Iteration behavior
- [ ] Preserve one-change-per-iteration doctrine
- [ ] Preserve commit-before-verify behavior
- [ ] Preserve verify/guard separation
- [ ] Define how the agent selects the next hypothesis
- [ ] Define stagnation/reflection threshold
- [ ] Define hard-stop threshold for repeated failures

### Keep/discard
- [ ] Define exact keep criteria
- [ ] Define exact discard criteria
- [ ] Define crash handling
- [ ] Define ambiguous-verify handling

### Logging
- [ ] Define run directory layout
- [ ] Define `target.yaml` schema
- [ ] Define `baseline.json` schema
- [ ] Define `results.tsv` schema
- [ ] Define `summary.md` expectations

---

## 5. Rollback and git safety checklist

- [ ] Remove destructive git reset fallback from the main control path
- [ ] Document non-destructive revert as the discard mechanism
- [ ] Ensure unrelated user changes are never reverted automatically
- [ ] Ensure the system works from a dirty worktree by isolating experiments safely
- [ ] Define experiment commit message convention
- [ ] Define how accepted run-branch results are merged or cherry-picked intentionally
- [ ] Define when the agent must stop due to unexpected external changes
- [ ] Add optional execpolicy rules for dangerous commands
- [ ] Add explicit approval boundaries for push/merge/publish/deploy/send actions

---

## 6. Planning/configuration checklist

- [ ] Convert planning workflow into a Codex skill
- [ ] Prefer infer-first setup over mandatory wizarding
- [ ] Ask only for missing required information
- [ ] Validate scope paths/globs
- [ ] Validate verify command availability
- [ ] Validate metric extraction strategy
- [ ] Validate direction (`higher`/`lower`)
- [ ] Validate optional guard command
- [ ] Emit machine-readable target config
- [ ] Emit human-readable summary for approval/review

---

## 7. Debug/fix/security/ship workflow checklist

### Debug
- [ ] Preserve hypothesis-driven investigation
- [ ] Preserve evidence requirement
- [ ] Remove interactive-tool dependence
- [ ] Define structured debug findings output
- [ ] Define chain behavior into fix workflow

### Fix
- [ ] Preserve one-fix-per-iteration rule
- [ ] Ensure error count must decrease to keep a change
- [ ] Define category targeting (test/type/lint/build)
- [ ] Define guard behavior on fix runs
- [ ] Define “done” as zero remaining target errors

### Security
- [ ] Keep default mode read-only
- [ ] Preserve evidence-based findings
- [ ] Replace Anthropic CLI/CI examples
- [ ] Define `--fail-on` severity behavior in runtime-neutral terms
- [ ] Define explicit opt-in for auto-remediation
- [ ] Define report artifact structure

### Ship
- [ ] Preserve phased readiness model
- [ ] Separate prepare/checklist vs execute/ship steps
- [ ] Require explicit approval for state-changing ship actions
- [ ] Define dry-run behavior
- [ ] Define rollback behavior
- [ ] Define monitor behavior
- [ ] Define checklist-only behavior

---

## 8. Scenario/predict redesign checklist

### Scenario
- [ ] Decide whether scenario belongs in v2 GA
- [ ] Remove heavy wizard dependence
- [ ] Define output format(s)
- [ ] Define stopping policy
- [ ] Keep it distinct from planning and debugging

### Predict
- [ ] Decide whether predict belongs in v2 GA
- [ ] Decide whether it should use Codex subagents
- [ ] Map current personas to explicit roles if subagents are used
- [ ] Define evidence format for each role
- [ ] Define consolidation format
- [ ] Avoid pseudo-persona fluff without operational value

---

## 9. Docs quality checklist

### Product docs
- [ ] Rewrite `README.md` as Codex-first
- [ ] Add a working quick start for Codex
- [ ] Show how to use `$autoresearch-plan`
- [ ] Show how to use `$autoresearch-loop`
- [ ] Show a repeatable target-file-based flow
- [ ] Document the verify/guard model clearly
- [ ] Document dirty-repo safety expectations

### Workflow docs
- [ ] Consolidate duplicated guide content into `docs/`
- [ ] Add one authoritative page per primary workflow
- [ ] Add migration notes for former Claude users
- [ ] Add troubleshooting guidance tied to real failure modes
- [ ] Add contributor docs for creating a new skill
- [ ] Add release docs for maintainers

### Documentation hygiene
- [ ] Remove or clearly label stale Claude-first docs
- [ ] Remove duplicated install instructions
- [ ] Remove duplicated command tables where possible
- [ ] Ensure examples match the new Codex structure exactly
- [ ] Ensure file paths in docs reflect the actual repo after migration

---

## 10. Command/skill restructuring checklist

- [ ] Stop treating `commands/` as the primary reusable workflow surface
- [ ] Move reusable workflow logic into `.agents/skills/`
- [ ] Move durable repo doctrine into `AGENTS.md`
- [ ] Split current `SKILL.md` responsibilities across:
  - [ ] `AGENTS.md`
  - [ ] per-workflow `SKILL.md`
  - [ ] optional reference docs
- [ ] Decide whether any legacy command wrappers remain at all
- [ ] If legacy wrappers remain, isolate them under `legacy/claude/`
- [ ] Ensure no new behavior is implemented only in legacy wrappers

---

## 11. Validation/testing checklist

### Static validation
- [ ] Add a validator for skill metadata
- [ ] Add a validator for broken reference paths
- [ ] Add a validator for forbidden legacy strings in non-legacy files
- [ ] Add a validator for target-file examples if schema is defined
- [ ] Add markdown link/path checks for docs

### Smoke tests
- [ ] Add a fixture repo for core improvement loop
- [ ] Add a fixture repo for dirty-worktree handling
- [ ] Add a fixture repo for failing-tests / fix workflow
- [ ] Add a fixture repo for debug evidence logging
- [ ] Add a fixture repo for security report generation
- [ ] Add a fixture repo for ship checklist generation

### Human validation
- [ ] Perform a first-time user run from README only
- [ ] Perform a contributor add-a-skill dry run
- [ ] Perform a maintainer release dry run

---

## 12. UX/setup checklist

- [ ] Ensure the onboarding path does not require prior Claude knowledge
- [ ] Ensure the project trust requirement is documented
- [ ] Ensure skill discovery is documented
- [ ] Ensure target config creation is documented
- [ ] Ensure where logs live is obvious
- [ ] Ensure how to stop/resume a run is documented
- [ ] Ensure how to review kept vs discarded experiments is documented
- [ ] Ensure how to handle dirty local changes is documented
- [ ] Ensure examples use realistic prompts and repository goals

---

## 13. Safety/rollback checklist

- [ ] Document destructive-command boundaries
- [ ] Document approval boundaries
- [ ] Document read-only defaults for security analysis
- [ ] Document auto-remediation opt-in boundaries
- [ ] Document how the agent behaves when unrelated changes are detected
- [ ] Document when the loop must stop instead of improvising
- [ ] Add optional rules for risky commands outside the sandbox
- [ ] Ensure logs do not encourage secret capture
- [ ] Ensure rollback guidance never recommends destructive cleanup as routine practice

---

## 14. Release readiness checklist

### Versioning
- [ ] Decide whether this is `v2.0.0`
- [ ] Update all visible version references consistently
- [ ] Remove duplicated version source-of-truth confusion

### Release process
- [ ] Rewrite release script to treat Codex-first assets as canonical
- [ ] Update release docs
- [ ] Confirm release flow does not depend on hidden `.claude/` sync unless intentional
- [ ] Confirm legacy bundle behavior if still shipped

### Release notes
- [ ] Explain that the repo is now Codex-first
- [ ] Explain where Claude legacy assets moved, if retained
- [ ] Explain the new skill-based workflow
- [ ] Explain the new target/run directory model
- [ ] Explain any breaking changes to command syntax or distribution

---

## 15. Final go/no-go checklist

Ship the Codex adaptation only when:

- [ ] Codex can use the repo without Claude plugin machinery
- [ ] the core loop is functional and safe
- [ ] logging and rollback are structured and inspectable
- [ ] docs are accurate and Codex-first
- [ ] maintainers have a believable release path
- [ ] contributors can extend the system without guessing
- [ ] the result feels like a designed Codex system, not a string-replaced Claude port
