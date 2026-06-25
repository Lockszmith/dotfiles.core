# Terminology

## Chezmoi

### chezmoi repo (git root)

`/home/sz/.local/share/chezmoi` — the git repository. Contains bootstrap files, `chezmoi.roots/`, docs, and agent config. Not the same as the active chezmoi source root.

### chezmoi source

Files chezmoi manages **from**. The active root is selected by `.chezmoiroot` (currently `chezmoi.roots/_home`).

```
chezmoi.roots/
├── _home/          ← active POSIX source root
├── _home.windows/  ← Windows source root
├── _src.all/       ← shared files (symlinked into roots)
└── __root_links/   ← OS → root selection
```

**Edit chezmoi source** when you want changes to survive `chezmoi apply` and be committed to git.

### chezmoi target

The live home directory (`$HOME`, e.g. `/home/sz`). Chezmoi **writes** here on apply.

**Do not edit chezmoi target** for persistent configuration. Exception: user explicitly requests a one-off hotfix and understands it will be overwritten or needs `chezmoi re-add`.

### Source → target name mapping

Chezmoi encodes target paths and file behaviour in **source state attributes** (filename prefixes and suffixes). Do not duplicate those rules here — use the official references:

- [Source state attributes](https://www.chezmoi.io/reference/source-state-attributes/) — full prefix/suffix table and ordering rules
- [How chezmoi works](https://www.chezmoi.io/concepts/how-chezmoi-works/) — source state → target overview
- [Target types](https://www.chezmoi.io/reference/target-types/) — files, directories, scripts, symlinks

Inspect or change attributes with `chezmoi chattr` rather than guessing rename rules.

**Repo example:** `chezmoi.roots/_home/private_dot_config/private_home-manager/` → `~/.config/home-manager/`

## Home-manager

### HM source

`chezmoi.roots/_home/private_dot_config/private_home-manager/` — version-controlled home-manager config deployed by chezmoi.

### HM target

`~/.config/home-manager/` — live tree used by `nix run` / `home-manager switch`. Mirrors HM source after `chezmoi apply`.

When the VS Code workspace shows both folders, **always edit HM source** unless applying a deliberate ephemeral test in target (then sync back to source).

### HM flag gating

Host config (`hosts/sz.nix.tmpl`) and the entire `home-manager/` tree are only managed when chezmoi flag `with-nix-hm` is set in `sz.env` flags. See `_home/.chezmoiignore`.

## Workspace folders

`.vscode/chezmoi.code-workspace` opens:

1. **chezmoi** — repo root (includes source under `chezmoi.roots/`)
2. **home-manager** — HM **target** (`~/.config/home-manager`)

Agents must not confuse the workspace "home-manager" folder with HM source.
