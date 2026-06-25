---
name: home-manager-config
description: Manages Nix home-manager modules, flake inputs, sz.* options, and switch workflows. Use when adding packages, services, desktop config, or editing private_home-manager in this chezmoi repository.
---

# Home-manager specialist

## Scope

**HM source** (edit here):

`chezmoi.roots/_home/private_dot_config/private_home-manager/`

**HM target** (apply destination): `~/.config/home-manager/`

## Procedure

1. Edit HM source only.
2. Follow `sz.*` module pattern (`options` + `lib.mkIf cfg.enable`).
3. Import new modules in `modules/default.nix`.
4. Add flag to `szEnv.nix-hm.yaml` (correct group/order per yaml notes); add enable line in `hosts/sz.nix.tmpl` at matching position.
5. Note: `flake.lock` gitignored — user runs `nix flake lock` after input changes.
6. Validate: `nix build .#homeConfigurations.sz.activationPackage`
7. Switch: `home-manager switch --flake .#sz`

## Chezmoi sync

After HM source edits → `chezmoi apply` syncs to target before nix build.

## Reference

`docs/agents/home-manager.md`

## Hand off

Return summary for **dotfiles-verifier**: goal, modules touched, flag added (yaml + sz.nix.tmpl), build result.
