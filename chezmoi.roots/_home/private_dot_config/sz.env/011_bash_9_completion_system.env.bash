#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

# if bash-complesion exists, no need
if [ -z "$(type -t _get_comp_words_by_ref)" ]; then
    update-bash-completion() {
        [[ -n "${DBG}" ]] && set -x
        local workdir="$SZ_ENV_ROOT/lib"
        rm -fR "$workdir/bash-completion*"
        mkdir -p "$workdir"
        
        ( cd "$workdir" \
            && curl -sL https://github.com/scop/bash-completion/releases/download/2.16.0/bash-completion-2.16.0.tar.xz \
            | xz -d \
            | tar x \
        && ln -sr bash-completion-* bash-completion.url
        )

        local script="$workdir/bash-completion/bash_completion"
        ! [ -r "$script.sh" ] || source "$script.sh" 2>/dev/null
        ! [ -r "$script"    ] || source "$script"    2>/dev/null
        [[ -n "${DBG}" ]] && set +x
    }

    [[ -n "${DBG}" ]] && set -x
    BC_PATH="$SZ_ENV_ROOT/lib/bash-completion.url"
    [ -r "$BC_PATH/bash_completion.sh" ] || [ -r "$BC_PATH/bash_completion" ] || BC_PATH="$HOMEBREW_PREFIX/etc/profile.d"
    [ -r "$BC_PATH/bash_completion.sh" ] || [ -r "$BC_PATH/bash_completion" ] || BC_PATH=""

    if [ -n "$BC_PATH" ]; then
        ! [ -r "$BC_PATH/bash_completion.sh" ] || source "$BC_PATH/bash_completion.sh" 2>/dev/null
        ! [ -r "$BC_PATH/bash_completion"    ] || source "$BC_PATH/bash_completion"    2>/dev/null
    else
        echo "bash-completion was not found, run update-bash-completion for a local install"
    fi

    if  [[ -n "${DBG}" && -n "$(type -t _get_comp_words_by_ref)" ]]; then
        echo "bash-completion loaded."
    fi
    [[ -n "${DBG}" ]] && set +x
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:

