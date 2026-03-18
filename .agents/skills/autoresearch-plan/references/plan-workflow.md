# Planning workflow

## Prompt shape
Prefer this input format:
- Goal:
- Context:
- Constraints:
- Done when:

## Planning order
1. Infer first.
2. Ask only for missing required information.
3. Validate the proposed target.
4. Save the target.
5. Summarize the plan in human language.

## Validation rules
A target is invalid when:
- scope is empty or obviously too broad for the goal
- verify command is missing
- metric direction is missing
- extractor is missing or ambiguous
- numeric stopping values are not positive integers

## Good defaults
- `max_iterations: 10`
- `stagnation_reflect_after: 5`
- `stop_after_consecutive_failures: 10`
- no guard unless there is a clear safety net worth keeping green
