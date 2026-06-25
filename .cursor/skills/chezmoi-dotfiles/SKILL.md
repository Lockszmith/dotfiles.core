---
name: chezmoi-dotfiles
description: Manages chezmoi source dotfiles, templates, sz.env flags, multi-root layout, and apply workflows. Use when editing chezmoi.roots, adding dotfiles, templates, externals, or running chezmoi diff/apply in this repository.
---

# Chezmoi dotfiles specialist

## Scope

**chezmoi source**: `chezmoi.roots/_home/`, `_src.all/`, active-root `.chezmoi.toml.tmpl`, `.chezmoiignore`, `.chezmoiexternal.yaml.tmpl`

**Never** persist edits in **chezmoi target** (`$HOME`) without mirroring to source.

## Procedure

1. Confirm file belongs in active root vs `_src.all` vs bootstrap (repo root).
2. Use correct source prefix for target path (see `docs/agents/terminology.md`).
3. For templates: reuse `.chezmoidata/` and `.chezmoitemplates/` patterns.
4. Edit source files only.
5. Suggest `chezmoi diff` / `chezmoi apply` (or `czu` for full update).

## Commands

| Action         | Command                                       |
| -------------- | --------------------------------------------- |
| Drift          | `chezmoi diff`                                |
| Apply          | `chezmoi apply`                               |
| With externals | `CZ_EXTR=1 chezmoi apply --include externals` |
| Add file       | `chezmoi add <target-path>`                   |

## Reference

`docs/agents/chezmoi.md`

## Hand off

When done, return summary for **dotfiles-verifier**: goal, files changed, expected target mappings, commands to run.
