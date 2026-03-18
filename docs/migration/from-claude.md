# Migration from the previous Claude-oriented layout

This repo now treats Codex-native surfaces as primary:
- `AGENTS.md`
- `.codex/config.toml`
- `.agents/skills/`
- `.autoresearch/targets/`
- `.autoresearch/runs/`

What changed:
- workflow entrypoints are skill-oriented
- repository doctrine lives in `AGENTS.md`
- target files are reusable and explicit
- run state is stored per run instead of in a single flat log
- destructive cleanup is not part of the normal discard path

What is deferred:
- `autoresearch-scenario`
- `autoresearch-predict`

A compatibility bundle is not shipped in this repo snapshot.
