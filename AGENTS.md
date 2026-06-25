# Agent instructions — dotfiles (chezmoi + home-manager)

Universal entry point for AI agents (Cursor, Claude Code, Codex, Antigravity, etc.).
Tool-specific config lives in `.cursor/`; portable knowledge lives in `docs/agents/`.

## Repository layout

| Area                                      | Path                                                           |
| ----------------------------------------- | -------------------------------------------------------------- |
| Git / chezmoi repo root                   | `/home/$USER/.local/share/chezmoi`                             |
| Active chezmoi **source** root            | `chezmoi.roots/_home/`                                         |
| Shared chezmoi source                     | `chezmoi.roots/_src.all/`                                      |
| Home-manager **source** (chezmoi-managed) | `chezmoi.roots/_home/private_dot_config/private_home-manager/` |
| VS Code workspace                         | `.vscode/chezmoi.code-workspace`                               |

## Terminology (mandatory)

Use these terms consistently. Full definitions: [docs/agents/terminology.md](docs/agents/terminology.md).

| Term               | Meaning                                                                                                                                  |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **chezmoi source** | Version-controlled files chezmoi reads (under active root). Edit here for persistent dotfile changes.                                    |
| **chezmoi target** | Live home directory (`$HOME`). Result of `chezmoi apply`. Do not edit for persistence unless the user explicitly wants a one-off hotfix. |
| **HM source**      | Home-manager tree inside chezmoi source (`private_dot_config/private_home-manager/`).                                                    |
| **HM target**      | `~/.config/home-manager/`. Applied copy; may drift until `chezmoi apply`.                                                                |

**Rule:** Persistent changes → edit **source**, then apply. Never commit edits made only in **target** paths.

## Sub-agent orchestration (required workflow)

Every non-trivial task uses three roles. In tools with sub-agents/tasks, launch them explicitly and **in parallel** when work is independent. In tools without, execute the same sequence in order.

```
User prompt
    → Orchestrator (route + briefs only — never implement)
        → Specialist(s) in parallel when independent:
            chezmoi-dotfiles | home-manager-config | agent-logic
        → Verifier(s) last:
            dotfiles-verifier | agent-logic-verifier
                → pass: done
                → fail: specialist fixes → re-verify (loop until pass)
```

### 1. Orchestrator

Read [docs/agents/orchestration.md](docs/agents/orchestration.md) or skill `.cursor/skills/dotfiles-orchestrator/SKILL.md`.

- Classify: chezmoi-only, HM-only, or both.
- State which **source** paths will be edited.
- Hand off a one-paragraph brief to the specialist.

### 2. Specialist

| Domain                                       | When                                                     | Skill / doc                                                                                        |
| -------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Dotfiles, templates, `sz.env`, chezmoi roots | Paths under `chezmoi.roots/`, `.chezmoi.toml`, externals | `.cursor/skills/chezmoi-dotfiles/` · [docs/agents/chezmoi.md](docs/agents/chezmoi.md)              |
| Nix modules, flake, packages, services       | `private_home-manager/`, `sz.*` options                  | `.cursor/skills/home-manager-config/` · [docs/agents/home-manager.md](docs/agents/home-manager.md) |
| Agent instructions, skills, orchestration    | `AGENTS.md`, `docs/agents/`, `.cursor/`                  | `.cursor/skills/agent-logic/` · [docs/agents/agent-logic.md](docs/agents/agent-logic.md)           |

### 3. Verifier (always last)

Read [docs/agents/verifier.md](docs/agents/verifier.md).

| Domain                 | Skill                                  |
| ---------------------- | -------------------------------------- |
| Chezmoi / home-manager | `.cursor/skills/dotfiles-verifier/`    |
| Agent scaffolding      | `.cursor/skills/agent-logic-verifier/` |

- Confirm outcome matches the **original user request**.
- Confirm edits are in **source** paths, not target-only.
- Run validation commands when applicable (`nix flake check`, `chezmoi verify`, etc.).
- On failure: return actionable gaps to the specialist; do not mark complete.

## Sub-agent parallelism (mandatory)

All implementation by sub-agents — the orchestrator never edits source files or runs domain commands itself.

- **Maximize parallel launches** — independent specialists in one turn (e.g. chezmoi + HM; unrelated file groups)
- **Master minimizes context** — orchestrator reads only what routing requires; specialists own investigation and edits
- **Route agent-logic tasks** — changes to `AGENTS.md`, `docs/agents/`, `.cursor/skills/`, `.cursor/rules/` → agent-logic specialist
- Verifier still runs last (once per task or per parallel batch, as appropriate)

## Quick routing

| User intent                                          | Specialist                                               |
| ---------------------------------------------------- | -------------------------------------------------------- |
| Shell alias, starship, zellij, ssh, vim, new dotfile | chezmoi-dotfiles                                         |
| New package, service, desktop option, flake input    | home-manager-config                                      |
| "Apply my dotfiles" / sync target                    | chezmoi-dotfiles                                         |
| `home-manager switch` / rebuild HM                   | home-manager-config                                      |
| Agent instructions, skills, orchestration docs       | agent-logic                                              |
| Unclear                                              | Orchestrator asks; default to chezmoi if no Nix involved |

## Safety

- No secrets, tokens, or employer-specific data in the repo.
- `flake.lock` and `result` are local/generated — do not commit.
- Home-manager is gated by chezmoi flag `with-nix-hm` in `sz.env` flags.
- Minimize diff scope; match existing module and naming conventions (`sz.*`).

## Reference index

- [docs/agents/README.md](docs/agents/README.md) — index
- [docs/agents/terminology.md](docs/agents/terminology.md)
- [docs/agents/chezmoi.md](docs/agents/chezmoi.md)
- [docs/agents/home-manager.md](docs/agents/home-manager.md)
- [docs/agents/orchestration.md](docs/agents/orchestration.md)
- [docs/agents/verifier.md](docs/agents/verifier.md)
- [docs/agents/agent-logic.md](docs/agents/agent-logic.md)
