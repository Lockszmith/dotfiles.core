# README.md of chezmoi repo

This is my chezmoi dotfiles repo

## One line install

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply https://code.lksz.me/lksz/dotfiles.git
```

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
is missing, chezmoi should be able to grab.

NEVER store personal identifying secrets/details or work/employer
specific details in the repo.

Assume others will be interested in investigating/cloning this
envrionment (I know, a bit arrogant), so keep it as generic as possible,
so it can be shared.

## Repo structure

The root dir of the repo is for documentation/orientation, as little
content as possible.

It contains:

* A 'throwaway' chezmoi bootstrap environment:

  ```
  .chezmoiscripts/
  .chezmoi.toml.tmpl
  .chezmoiignore
  .gitignore
  ```
* This `README.md` and a `docs` directory for additional documentation.
* `chezmoi.roots` containing environment specific chezmoi roots.

## Bootstrap

`.chezmoiroot` points to the source-state of the current envrionments.  
I creted this so I can ensure I have the necessary tooling to
effectively initialize an envrionment assuming as little as possible.

Initializing the bootstrap envrionment, detects the macine type,
generates the `.chezmoiroot`, scraps the bootstrap configuration and
initializes chezmoi now that `.chezmoiroot` exitst.

This is why `.gitignore` ignores `.chezmoiroot`, as it is different on
every machine.

## The Different Envrionments

At this point Home and Home.MacOS are almost identical and they will
probably be merged in the future.

I crated the MacOS envionrment when I was unsure about the differences,
wanting to separate the envrionments while I currate them.

Both are POSIX based (to a degree), and my expectation for them is to
behave in as similar a manner as possible.

To make the envrionments 'inherit' from one another, I've written
`symclone.sh`, a tool script that creats symlinks across different
chezmoi environments.

For more information abot each envrionment, see their respective (WIP)
`README.md` files.

