---
name: dotfiles-verifier
description: Validates chezmoi and home-manager work matches the user request, edits are in source paths, and builds pass. Use after every chezmoi-dotfiles or home-manager-config task; re-run specialist on failure until PASS.
---

# Dotfiles verifier

## When

Always run **after** chezmoi-dotfiles or home-manager-config specialist completes. Loop: FAIL → specialist fixes → re-verify.

For **agent-logic** tasks (changes to `AGENTS.md`, `docs/agents/`, `.cursor/skills/`, `.cursor/rules/`), use `agent-logic-verifier` instead (or in addition for mixed tasks).

## Checklist

### Request match
- [ ] Delivered outcome matches **original user request**
- [ ] Minimal diff; no unrelated changes

### Source-path audit
- [ ] Chezmoi edits in `chezmoi.roots/`, not bare `$HOME`
- [ ] HM edits in `private_dot_config/private_home-manager/`, not target-only

### Chezmoi (if applicable)
- [ ] Prefixes/templates correct
- [ ] Flag conditionals intact (`with-nix-hm`, etc.)
- [ ] Run `chezmoi diff` when possible

### Home-manager (if applicable)
- [ ] Module imported + enabled as needed
- [ ] New module: flag in `szEnv.nix-hm.yaml` at correct sort position + enable line in `hosts/sz.nix.tmpl` in matching order (see yaml notes)
- [ ] `sz.*` namespace for custom options
- [ ] Run `nix build .#homeConfigurations.sz.activationPackage` when possible

### Safety
- [ ] No secrets committed

## Output

Use report template in `docs/agents/verifier.md`.

**PASS** → brief summary + user commands (`chezmoi apply`, `home-manager switch`).

**FAIL** → numbered gaps + required fixes for specialist; do not mark complete.

## Reference

`docs/agents/verifier.md`
