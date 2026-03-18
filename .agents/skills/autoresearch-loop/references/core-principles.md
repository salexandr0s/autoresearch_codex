# Core principles

The Codex-first autoresearch loop keeps these rules invariant:

1. Read before write.
2. One change per iteration.
3. Mechanical verification only.
4. Git is experiment memory.
5. Safety beats cleverness.
6. Keep only what earns its place.
7. Every kept or discarded experiment must stay explainable.

Operational consequences:
- do not skip baseline measurement
- do not keep a change with an unparseable metric
- do not auto-clean unrelated user work
- do not widen scope mid-run without explicit approval
- do not confuse a plausible explanation with a verified result
