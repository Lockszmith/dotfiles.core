# Agent logic

Portable reference for editing AI agent scaffolding in this repository. Tool-specific files mirror this content; they must not become the canonical source.

## Scope

| File / area                       | Role                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------- |
| `AGENTS.md`                       | Universal entry point: layout, terminology, routing, safety                     |
| `docs/agents/*.md`                | Domain and workflow docs (chezmoi, HM, orchestration, verifier, agent-logic, …) |
| `docs/agents/README.md`           | Index of portable docs                                                          |
| `.cursor/skills/*/SKILL.md`       | Cursor specialist skills (YAML frontmatter + concise steps)                     |
| `.cursor/rules/*.mdc`             | Cursor rules (globs + brief reminders)                                          |
| `CLAUDE.md`                       | Claude Code pointer → `AGENTS.md`                                               |
| `.github/copilot-instructions.md` | GitHub Copilot pointer → `AGENTS.md`                                            |

Out of scope here: chezmoi source, home-manager modules — see [chezmoi.md](chezmoi.md) and [home-manager.md](home-manager.md).

## Layering

### Portable layer

Lives in `AGENTS.md` and `docs/agents/`.

- Procedures any agent can follow without Cursor
- Terminology, routing tables, checklists, handoff templates
- Tool mapping in optional tables (e.g. [orchestration.md](orchestration.md)) — describe roles, not IDE features as requirements

### Tool-specific layer

Lives under `.cursor/`.

- Skill `name` / `description`, sub-agent launch patterns, rule `globs`
- Short summaries that **link** to portable docs
- Never the only place for a procedure the whole repo depends on

### Pointer layer

`CLAUDE.md` and `.github/copilot-instructions.md`.

- One or two sentences directing agents to `AGENTS.md` and `docs/agents/`
- No duplicated tables or workflows

## Workflow

1. **Identify layer** — portable doc, AGENTS.md summary, Cursor skill/rule, or pointer file.
2. **Edit portable first** — add or change canonical content in `docs/agents/` (or `AGENTS.md` for top-level routing).
3. **Sync tool layer** — update matching skill/rule to reference the portable doc; trim copied prose.
4. **Update indexes** — add row to `docs/agents/README.md`; extend `AGENTS.md` routing if a new specialist exists.
5. **Orchestration** — if roles or handoffs change, update [orchestration.md](orchestration.md) and the orchestrator skill/rule routing tables.
6. **Verify** — run `agent-logic-verifier` (or [verifier.md](verifier.md) Agent-logic checks); use `dotfiles-verifier` only if dotfile/HM instructions changed.

### Adding a new specialist

1. Create `docs/agents/<name>.md` (portable procedures).
2. Create `.cursor/skills/<name>/SKILL.md` (≤ 500 lines, links to portable doc).
3. Optionally create `.cursor/rules/<name>.mdc` with globs for affected paths.
4. Add routing rows in `AGENTS.md` and [orchestration.md](orchestration.md).

## Agent-agnostic checklist

Before marking agent-scaffolding work complete:

- [ ] **Portable purity** — `docs/agents/` and `AGENTS.md` contain no Cursor-only APIs, skill paths as requirements, or `.mdc` mechanics as normative steps
- [ ] **Single source of truth** — detailed procedures live in one portable doc; skills/rules only add tool-specific steps
- [ ] **Cross-references** — links use relative paths; no copy-pasted sections between portable and tool files
- [ ] **Index updated** — new portable docs listed in [README.md](README.md)
- [ ] **Pointers minimal** — `CLAUDE.md` and `copilot-instructions.md` still short link-only files
- [ ] **Skill size** — each `SKILL.md` under 500 lines
- [ ] **Routing consistent** — `AGENTS.md`, orchestration doc, and orchestrator skill agree on specialist names and when to use them
- [ ] **Terminology** — use [terminology.md](terminology.md) terms (chezmoi source/target, HM source/target) where dotfiles are involved

## Related

- [orchestration.md](orchestration.md) — roles, handoffs, tool mapping
- [verifier.md](verifier.md) — post-task validation for dotfile/HM work
- [README.md](README.md) — doc index
