# Troubleshooting

## The repo is not a git repository

`autoresearch-loop` should stop with a blocked summary if the task needs experiment commits or reverts. Initialize git before running the full loop.

## The metric is ambiguous

Fix the target's extractor. Do not keep changes on ambiguous verification.

## The repo is dirty

Prefer a dedicated worktree so unrelated changes stay untouched.

## The guard always fails

Treat the run as blocked until the guard or target definition is corrected.
