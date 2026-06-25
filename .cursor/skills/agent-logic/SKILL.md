---
name: agent-logic
description: Edits agent scaffolding (AGENTS.md, docs/agents/, skills, rules, pointer files) in an agent-agnostic way. Use when changing agent instructions, orchestration, specialist skills, Cursor rules, or tool entry-point files in this repository.
---

# Agent-logic specialist

## Scope

| Layer             | Paths                                          | Content                                                           |
| ----------------- | ---------------------------------------------- | ----------------------------------------------------------------- |
| **Portable**      | `AGENTS.md`, `docs/agents/**`                  | Universal procedures, routing, terminology, checklists            |
| **Tool-specific** | `.cursor/skills/**`, `.cursor/rules/**`        | Cursor skills and rules; mirror portable docs, add tool mechanics |
| **Pointer files** | `CLAUDE.md`, `.github/copilot-instructions.md` | Short links to `AGENTS.md` and `docs/agents/` only                |

Do **not** edit chezmoi dotfiles or home-manager config here — route to `chezmoi-dotfiles` or `home-manager-config`.

## Principles

1. **Portable first** — canonical knowledge lives in `docs/agents/` and summary tables in `AGENTS.md`.
2. **Tool-specific stays local** — Cursor sub-agents, `Task` tool, `.mdc` globs, skill YAML → `.cursor/` only.
3. **No Cursor-only concepts in portable docs** — write "sub-agent", "specialist", "verifier"; map tools in a separate table if needed (see `docs/agents/orchestration.md`).
4. **Cross-reference, don't duplicate** — link to `docs/agents/<topic>.md`; skills/rules add WHEN + tool steps, not full procedures.
5. **Skills ≤ 500 lines** — trim or split; move detail to `docs/agents/`.
6. **Pointer files stay minimal** — one or two sentences + links; never duplicate AGENTS.md body.

## Procedure

1. Classify change: portable doc, tool skill/rule, pointer file, or routing/orchestration.
2. Edit **portable** content in `docs/agents/` (or `AGENTS.md` for entry-point summary).
3. If Cursor needs it: update matching skill/rule to reference the portable doc — do not copy long sections.
4. Update indexes: `docs/agents/README.md` for new docs; `AGENTS.md` routing table if new specialist.
5. Keep orchestration invariant: specialist work → verifier when the change affects dotfile/HM workflows.
6. For new specialist: add portable doc, skill, optional rule with globs, row in `AGENTS.md` and `docs/agents/orchestration.md`.

## Skill format

```yaml
---
name: kebab-case-name
description: <WHAT in third person>. <WHEN to use — trigger phrases>.
---
```

Body: scope, steps, reference link to `docs/agents/<name>.md`, handoff notes if applicable.

## Rule format (`.mdc`)

```yaml
---
description: One-line summary
globs: path/pattern
alwaysApply: false
---
```

Brief reminders + link to skill and portable doc. No long duplicated checklists.

## Checklist before finishing

- [ ] Portable docs contain no Cursor-only APIs or `.cursor/` path requirements as normative text
- [ ] Skills/rules link to portable docs; duplicated prose removed
- [ ] `docs/agents/README.md` indexes new portable docs
- [ ] Pointer files unchanged unless adding a new tool entry point
- [ ] Skill file under 500 lines

## Reference

- `docs/agents/agent-logic.md` — portable editing guide
- `docs/agents/orchestration.md` — roles and handoffs
- `AGENTS.md` — universal entry point

## Hand off

Return summary for **agent-logic-verifier**: files changed, layer (portable / tool / pointer), and whether `dotfiles-verifier` is also needed.
