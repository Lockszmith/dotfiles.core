---
name: agent-logic-verifier
description: Validates agent scaffolding changes match the request, preserve portable vs tool-specific layering, and keep orchestration references consistent. Use after agent-logic specialist tasks or when editing AGENTS.md, docs/agents/, or .cursor/skills/.
---

# Agent-logic verifier

## When

Always run **after** agent-logic specialist completes. Loop: FAIL → specialist fixes → re-verify.

For mixed tasks (agent-logic + chezmoi/HM), run **both** this skill and `dotfiles-verifier` as appropriate.

## Checklist

### Request match
- [ ] Delivered outcome matches **original user request**
- [ ] Minimal diff; no unrelated changes

### Portable vs tool-specific layering
- [ ] Portable knowledge in `docs/agents/` and `AGENTS.md`
- [ ] Cursor-specific content in `.cursor/skills/` and `.cursor/rules/` only
- [ ] No Cursor-only deps (Task subagent, skill paths) in `docs/agents/` or `AGENTS.md`

### Pointer files
- [ ] `CLAUDE.md` still points to `AGENTS.md`
- [ ] `.github/copilot-instructions.md` still points to `AGENTS.md`

### Skills and docs consistency
- [ ] New/changed skills have valid YAML frontmatter (`name`, `description` — third person, WHAT+WHEN)
- [ ] Orchestration flow in `docs/agents/orchestration.md` matches specialist → verifier routing
- [ ] Verifier references in orchestration, `AGENTS.md`, and domain skills are consistent
- [ ] `docs/agents/README.md` agent section updated when new skills or docs are added

### Safety
- [ ] No secrets committed

## Output

Use report template in `docs/agents/verifier.md` (Agent-logic checks section).

**PASS** → brief summary of what changed and which paths.

**FAIL** → numbered gaps + required fixes for agent-logic specialist; do not mark complete.

## Reference

- `docs/agents/verifier.md` — Agent-logic checks
- `docs/agents/orchestration.md` — routing and flow
