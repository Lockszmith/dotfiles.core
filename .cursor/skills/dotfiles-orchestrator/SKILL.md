---
name: dotfiles-orchestrator
description: Routes every dotfile and agent-logic prompt to parallel specialists and mandates verifier follow-up when Task/sub-agents are available. Use for any chezmoi, home-manager, dotfiles, agent scaffolding, or home directory configuration request in this repo.
---

# Dotfiles orchestrator

**Mandatory for every user prompt** when `Task`/sub-agents are available — orchestrator routes only; never implements.

## Steps

1. Read user request; restate goal in one sentence.
2. Classify:
   - **chezmoi** — paths under `chezmoi.roots/`, templates, `sz.env`, externals, apply/diff
   - **home-manager** — Nix modules, flake, `sz.*` options, switch/build
   - **agent-logic** — `AGENTS.md`, `docs/agents/`, `.cursor/skills/`, `.cursor/rules/`
   - **both / multiple** — decompose; launch independent specialists in parallel
3. Decompose into parallel sub-tasks where domains or file groups are independent.
4. List **source** paths per sub-task (see `docs/agents/terminology.md`).
5. Produce handoff brief(s) (template in `docs/agents/orchestration.md`).
6. **Launch independent specialists concurrently** in one turn — never implement in orchestrator.
7. Collect specialist results; invoke verifier(s) last:
   - `dotfiles-verifier` — chezmoi / HM work
   - `agent-logic-verifier` — agent scaffolding work
8. On verifier FAIL → send gaps to relevant specialist → re-verify until PASS.

## Parallelism rules

- chezmoi + HM simultaneously when edits do not depend on each other
- Multiple unrelated file groups → separate parallel sub-agents
- Orchestrator minimizes its own reads/edits — routing and briefs only

## Handoff

Pass to specialist:
- Goal, source paths, constraints (flags, scope), done-when criteria

## Reference

- `AGENTS.md`
- `docs/agents/orchestration.md`
