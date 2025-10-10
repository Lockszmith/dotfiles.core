#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

ZNAP_REPO="${XDG_DATA_HOME:-${HOME}/.local/share}/znap/_"

znap-cleanup() {
    printf '%s\n' ~/ ~/VAST/dockersh.home/ | xargs -I _ find _ -maxdepth 3 -type d -name 'znap' -or -name 'zsh-snap' -print -exec rm -fr '{}' +
}

# Download Znap, if it's not there yet.
[[ -r "${ZNAP_REPO}/znap.zsh" ]] ||
    git clone --depth 1 -- \
        https://github.com/marlonrichert/zsh-snap.git "${ZNAP_REPO}"
source "${ZNAP_REPO}/znap.zsh"  # Start Znap

