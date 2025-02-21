#! /usr/bin/env bash

set -ex

rm -fR ~/.config/chezmoi ~/.local/share/chezmoi/.chezmoiroot
chezmoi init --apply
