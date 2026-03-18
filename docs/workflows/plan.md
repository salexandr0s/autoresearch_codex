# autoresearch-plan

Use this workflow to turn a user goal into a validated target file.

## Input shape
- Goal:
- Context:
- Constraints:
- Done when:

## Responsibilities
- infer scope and commands from repo context first
- ask only for missing required information
- make metric direction explicit
- make extractor explicit
- save a reusable target under `.autoresearch/targets/`

## Required output
A valid target that `autoresearch-loop` can consume directly.
