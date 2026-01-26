# README.md of chezmoi repo

This is my chezmoi dotfiles repo

## One line install

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply https://code.lksz.me/dotfiles/core.git
```

* See [Try Me](#try_me) to test in a docker container.

## Why even bother?

I work on multiple platforms:
* Windows 11 - as my home PC (not covered directly by this repo... yet)
* TrueNAS SCALE/Linux servers (mine and my backup-buddy friend home-labs
  I manage/support)
* MacOS - Work MacBook Pro
* Linux - @Work log analysis tech servers, (on which I do not have root
  access).

This repo helps me keep these environments (excluding the
Windows/Powershell one for now) as comfortable and predictable for me as
possible.

## Philosophy / Design Guidelines

Do as much setup as possible at once, make maintenance simple, don't
slow down productivity (it's bad for my ADHD).

If a tool is missing, find a single-binary solution that can be managed
by `.chezmoiexternals`. **rust** and **go** based tools are best for
this.

Assume a system has `bash`, `git`, `curl` or `wget`, anything else that
is missing, chezmoi should be able to grab or handle without it.

NEVER store personal identifying secrets/details or work/employer
specific details in the repo.

Assume others will be interested in investigating/cloning this
envrionment (I know, a bit arrogant), so keep it as generic as possible,
so it can be shared.

Modularity and configurability - be able to control how the system
installs by considering different 'modules' (or group of functionality)
that can be switched on/off in the .chezmoi.toml configuration file.

## Repo structure

The root dir of the repo is for documentation/orientation, as little
content as possible.

It contains:

* This `README.md` and a `docs` directory for additional documentation.
* `chezmoi.roots` containing environment specific chezmoi roots.
* A 'throwaway' chezmoi bootstrap environment (more details below)

## Bootstrap

* The files:

  ```
  .init.me.sh
  .chezmoiscripts/run_init.ps1.tmpl
  .chezmoi.toml.tmpl
  .chezmoiignore
  .gitignore
  ```

`.init.me.sh` a script to re-initialize environment. Cleans up chezmoi
state and goes through `chezmoi init` process.

`.chezmoi.toml.tmpl` this is the bootstrap configuration template that
handles the initial system detection and props chezmoi to run the auto
intialization script.

`.chezmoiignore` makes sure chezmoi only considers the above listed
files as the source of truth (this is for the temporary bootstrap
invocation only) - it **ignores** `.chezmoiroot` as that is unique to
the active envrionment.

`.chezmoiscripts/run_init.ps1.tmpl` is the auto initialization script
that will generate `.chezmoiroot` based on further detection and 
uset-prompts. When it's done, it (on non-Windows) scraps the bootstrap
configuration and initoalizes the actual chezmoi envrionment.
(on Windows, it will prompt you with instructions on how to initialize)

The process above ensure I have the necessary tooling to effectively
initialize a full envrionment, while assuming as little as possible.

## The Different Envrionments

Currently existing:
* `_src.all`
* `_home`
* `_home.windows`

`_home` is the unix like environment (Linux, MacOS or WSL), and
`_home.windows` is for Windows.

`_src.all` is linked by all environment.

To make the envrionments 'inherit' from one another, I've written
`symclone.sh`, a tool script that creats symlinks across different
chezmoi environments.

For more information abot each envrionment, see their respective (WIP)
`README.md` files.

## Working within an active environment

`cz` is a shorthand to `chezmoi`
`czx` is `chezmoi` with the `.chezmoiexternals` context enabled.

`czu` a script to update the environment.
`czg` `cz git` with git autocompletion
`czed` shorthand for `chezmoi edit`
`czedext` edit the .chezmoiexternal.toml template
`czedignore` edit the .chezmoiignore template

`cz[x]s` `chezmoi status`
`cz[x]a` `chezmoi apply`

`cz-cd` cd into the chezmoi home dir
`czgcd` cd into the root of the chezmoi git repo

## Try Me

```
# Create a temporary home-dir, and start a docker image of your favorite distro
DISTRO=rockylinux/rockylinux:latest
TESTDIR="${TESTDIR:-$(mktemp --directory)}"; TE="$TESTDIR/.cache/tmp/etc"; mkdir -p "$TE"; cp /etc/passwd "$TE/p"; cp /etc/group "$TE/g"; docker run --rm --name temp-rocky -u $UID -v "$TE/p:/etc/passwd:ro" -v "$TE/g:/etc/group:ro" -v "$TESTDIR:$HOME" -w "$HOME" -it "$DISTRO" bash

# within the bash repo, intialize the chezmoi environment
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply https://code.lksz.me/dotfiles/core.git

# clear the temporary folder
rm -fR $TESTDIR && unset TESTDIR TE
```
