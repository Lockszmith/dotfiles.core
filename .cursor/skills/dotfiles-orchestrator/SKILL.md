---
name: dotfiles-orchestrator
description: Routes dotfile tasks to chezmoi or home-manager specialists and mandates verifier follow-up. Use for any chezmoi, home-manager, dotfiles, or home directory configuration request in this repo.
---

# Dotfiles orchestrator

## Steps

1. Read user request; restate goal in one sentence.
2. Classify:
   - **chezmoi** — paths under `chezmoi.roots/`, templates, `sz.env`, externals, apply/diff
   - **home-manager** — Nix modules, flake, `sz.*` options, switch/build
   - **both** — chezmoi first (HM is chezmoi-deployed), then HM
3. List **source** paths to edit (see `docs/agents/terminology.md`).
4. Produce handoff brief (template in `docs/agents/orchestration.md`).
5. Delegate to specialist skill/sub-agent — do not implement in orchestrator pass.
6. After specialist completes, **always** invoke `dotfiles-verifier`.
7. On verifier FAIL → send gaps to specialist → re-verify until PASS.

## Handoff

Pass to specialist:
- Goal, source paths, constraints (flags, scope), done-when criteria

## Reference

- `AGENTS.md`
- `docs/agents/orchestration.md`
