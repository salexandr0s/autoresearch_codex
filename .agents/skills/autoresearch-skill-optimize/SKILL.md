---
name: autoresearch-skill-optimize
description: Optimize a target SKILL.md with runner-backed test inputs, binary evals, baseline scoring, and keep/discard iteration discipline.
---

# autoresearch-skill-optimize

Use this workflow when you want `autoresearch` to improve a Codex `SKILL.md` mechanically rather than by vibes.

## Workflow
1. Validate the target `SKILL.md`, `inputs.yaml`, and `evals.yaml`.
2. Create a reusable autoresearch target with scope limited to the skill and any explicitly approved references.
3. Run a baseline verify pass before any mutation.
4. Iterate with one coherent hypothesis per change.
5. Keep only experiments that improve the scored pass rate.
6. Log scored outputs, decisions, and next moves under the run directory.

## Rules
- baseline first
- one change per iteration
- binary evals only
- no unrelated repo edits
- no destructive git cleanup
- stop on repeated ambiguity or failure
