# Chezmoi procedures

## Before editing

1. Identify whether the file lives in **chezmoi source** (`chezmoi.roots/_home/` or `_src.all/`) or **chezmoi target** (`$HOME`).
2. Edit **source** only for persistent changes.
3. Check if the path is a template (`*.tmpl`) — use Go template syntax and existing `.chezmoidata/` variables.

## Active root resolution

```bash
readlink -f /home/sz/.local/share/chezmoi/.chezmoiroot
# → chezmoi.roots/_home
```

## Common operations

| Task                         | Command                                                      |
| ---------------------------- | ------------------------------------------------------------ |
| See drift (source vs target) | `chezmoi diff` or `chezmoi status`                           |
| Apply changes                | `chezmoi apply` (alias `cza`)                                |
| Apply with externals         | `CZ_EXTR=1 chezmoi apply --include externals` (alias `czxa`) |
| Full update workflow         | `czu` (upgrade, pull, init, apply externals)                 |
| Edit a managed file          | `chezmoi edit ~/.path/to/file` or `czed`                     |
| Add untracked target file    | `chezmoi add ~/.path/to/file`                                |
| Verify integrity             | `chezmoi verify`                                             |

## Adding a new dotfile

1. Create file under active root using correct prefix, e.g. `dot_config/foo/config`:
   - Source: `chezmoi.roots/_home/private_dot_config/foo/config`
   - Target: `~/.config/foo/config`
2. Or: create in target → `chezmoi add ~/.config/foo/config` → move/rename in source if needed.
3. `chezmoi diff` → `chezmoi apply`.

## Templates

- Data: `chezmoi.roots/_home/.chezmoidata/` (`szEnv.yaml`, `zellij.yaml`, `prompt.yaml`)
- Fragments: `chezmoi.roots/_home/.chezmoitemplates/`
- Config template: `_src.all/.chezmoi.toml.tmpl` (prompts for identity, `sz.env` flags)

Flag checks in templates:

```go
{{- if has "with-nix-hm" (splitList " " (dig "sz" "env" "flags" "" .)) -}}
```

## Multi-root / shared files

- Shared across POSIX roots: put in `_src.all/`, symlink into `_home/` via `symclone.sh`.
- OS-specific: edit `_home/` or `_home.windows/` directly.

## Externals

Defined in `.chezmoiexternal.yaml.tmpl`. Require `CZ_EXTR=1` or `czx` prefix.

## Ignore rules

- Bootstrap: repo-root `.chezmoiignore`
- Active root: `chezmoi.roots/_home/.chezmoiignore` (conditional HM, VAST paths)

## Do not

- Commit secrets or machine-local paths.
- Edit bootstrap-only files (`/.chezmoi.toml.tmpl` at repo root) for normal dotfile work — use active root config.
- Assume `~/.config/home-manager` is source — see [terminology.md](terminology.md).
