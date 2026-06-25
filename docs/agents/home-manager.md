# Home-manager procedures

## Paths

| Role                      | Path                                                           |
| ------------------------- | -------------------------------------------------------------- |
| **HM source** (edit here) | `chezmoi.roots/_home/private_dot_config/private_home-manager/` |
| **HM target** (applied)   | `~/.config/home-manager/`                                      |

After editing HM source: `chezmoi apply` then rebuild HM.

## Architecture

```
flake.nix
  └── lib.mkHost { name = "sz"; }
        ├── modules/default.nix
        ├── hosts/default.nix
        ├── hosts/sz.nix          ← from sz.nix.tmpl (flag-gated)
        └── vicinae.homeManagerModules.default
```

Custom options namespace: `sz.*` (`sz.platform`, `sz.desktop`, `sz.packages`, `sz.activations`).

## Adding a package module

1. Create `modules/packages/<name>.nix`:

```nix
{ config, pkgs, lib, ... }:
let cfg = config.sz.packages.<name>;
in {
  options.sz.packages.<name>.enable = lib.mkEnableOption "<description>";
  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.<package> ];
  };
}
```

2. Import in `modules/default.nix`.
3. Enable in `hosts/sz.nix.tmpl`: `sz.packages.<name>.enable = true;`
4. Validate and switch (see below).

## Adding a flake input

1. Add to `inputs` in `private_executable_flake.nix` (HM source).
2. Pass through `outputs` → `lib` `extraSpecialArgs` if modules need it.
3. `nix flake lock` in HM target after apply (lockfile is gitignored).

## Build and switch

From HM target directory:

```bash
cd ~/.config/home-manager

# Evaluate without activating
nix build .#homeConfigurations.sz.activationPackage

# Activate
home-manager switch --flake .#sz
# or
nix run home-manager -- switch --flake .#sz
```

## Validation

```bash
cd ~/.config/home-manager
nix flake check          # if checks defined
nix build .#homeConfigurations.sz.activationPackage
```

## Chezmoi integration

- `hosts/sz.nix.tmpl` wrapped in `with-nix-hm` flag — empty host file when flag off.
- `flake.lock` ignored by chezmoi — regenerate locally.
- `result` symlink points to store generation — do not commit.

## Workflow after HM source edit

1. Edit files under `private_home-manager/` in chezmoi source.
2. `chezmoi diff` / `chezmoi apply` → syncs to `~/.config/home-manager/`.
3. `nix build` or `home-manager switch --flake .#sz`.
4. Verifier confirms package/service appears as requested.

## Do not

- Edit only `~/.config/home-manager/` without syncing back to HM source.
- Commit `flake.lock` or `result`.
- Use non-`sz.*` option namespace for custom toggles (except upstream `services.*`).
