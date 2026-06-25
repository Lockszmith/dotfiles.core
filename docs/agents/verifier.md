# Verifier

Runs **after** every specialist pass. Re-run specialist + verifier until all checks pass.

## Verification report template

```markdown
## Request
<original user goal>

## Result
PASS | FAIL

## Source-path audit
- [ ] All persistent edits in chezmoi source / HM source
- [ ] No target-only edits left unmirrored to source

## Domain checks
<chezmoi and/or HM checklist below>

## Gaps (if FAIL)
1. ...
## Required fixes
1. ...
```

## Universal checks

- [ ] Outcome matches **original user request** (not just "files were edited")
- [ ] Diff scope is minimal — no unrelated changes
- [ ] No secrets committed
- [ ] Terminology correct in any docs/comments added

## Chezmoi checks

- [ ] Files under `chezmoi.roots/_home/` or `_src.all/`, not bare `$HOME` edits
- [ ] Template syntax valid if `*.tmpl` changed
- [ ] Flag conditionals preserved (`with-nix-hm`, etc.)
- [ ] `chezmoi diff` shows expected target mappings (run when possible)

## Home-manager checks

- [ ] Edits in `private_dot_config/private_home-manager/` (HM source)
- [ ] New modules imported in `modules/default.nix`
- [ ] New module: flag added to `chezmoi.roots/_home/.chezmoidata/szEnv.nix-hm.yaml` (`choices.nixHomeManagerFlags`) at correct sort position
- [ ] Matching enable line in `hosts/sz.nix.tmpl` at same order as yaml (sub-lines for one flag, e.g. vicinae systemd, stay adjacent)
- [ ] `sz.*` option namespace used for custom toggles
- [ ] `nix build .#homeConfigurations.sz.activationPackage` succeeds (run when possible)

## Cross-domain checks

When HM source changed via chezmoi:

- [ ] `chezmoi apply` would sync HM source → HM target
- [ ] Rebuild command documented or run

## Agent-logic checks

For changes to `AGENTS.md`, `docs/agents/`, `.cursor/skills/`, or `.cursor/rules/`:

- [ ] Outcome matches **original user request**; minimal diff
- [ ] Portable content in `docs/agents/` and `AGENTS.md`; Cursor-specific in `.cursor/` only
- [ ] No Cursor-only deps (Task subagent, skill paths) in portable docs
- [ ] `CLAUDE.md` and `.github/copilot-instructions.md` still point to `AGENTS.md`
- [ ] Skills have valid frontmatter (`name`, `description` — third person, WHAT+WHEN)
- [ ] Orchestration/verifier references consistent (`orchestration.md`, `AGENTS.md`, skills)
- [ ] `docs/agents/README.md` updated when new agent docs or skills are added

Cursor skill: `.cursor/skills/agent-logic-verifier/SKILL.md`

## On FAIL

1. List specific gaps (not "looks wrong").
2. Assign fixes back to the **same** specialist role.
3. Re-run this checklist.
4. Do **not** tell the user the task is complete until PASS.

## On PASS

Summarize: what changed, which source paths, any apply/switch commands the user should run.
