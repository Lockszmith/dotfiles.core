#!/usr/bin/env -S bash -c 'echo "Not a user script. source(aka .) only"'

update-bash-preexec() {
    local workdir="$SZ_ENV_ROOT/lib/bash-preexec"
    [ -d "$workdir" ] && rm -fR "$workdir"
    mkdir -p "$workdir"
    
    cd "$workdir"

    # Pull down our file from GitHub and write it to your home directory as a hidden file.
    curl https://raw.githubusercontent.com/rcaloras/bash-preexec/master/bash-preexec.sh -o ./bash-preexec.sh
    # Source our file to bring it into our environment
    source .bash-preexec.sh
    
    source "$workdir/ble-nightly/ble.sh"
}

# shellcheck disable=SC1091 source=$HOME/.bash-preexec.sh
if [[ -f "$SZ_ENV_ROOT/lib/bash-preexec/.bash-preexec.sh" ]]; then
    SZ_ENV_BASH_LOAD_PREEXEC='. "$SZ_ENV_ROOT/lib/bash-preexec/.bash-preexec.sh"'

    [[ -n "${DBG}" ]] && echo "Bash-preexec will be loaded."
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
