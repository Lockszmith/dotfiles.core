---
name: dotfiles-verifier
description: Validates chezmoi and home-manager work matches the user request, edits are in source paths, and builds pass. Use after every chezmoi-dotfiles or home-manager-config task; re-run specialist on failure until PASS.
---

# Dotfiles verifier

## When

Always run **after** specialist completes. Loop: FAIL → specialist fixes → re-verify.

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
