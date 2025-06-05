#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

ZNAP_REPO="${XDG_DATA_HOME:-${HOME}/.local/share}/znap/_"

# Download Znap, if it's not there yet.
[[ -r "${ZNAP_REPO}/znap.zsh" ]] ||
    git clone --depth 1 -- \
        https://github.com/marlonrichert/zsh-snap.git "${ZNAP_REPO}"
source "${ZNAP_REPO}/znap.zsh"  # Start Znap

