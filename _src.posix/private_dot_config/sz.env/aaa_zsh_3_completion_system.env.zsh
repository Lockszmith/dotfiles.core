#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

BASE_SHELL=${BASE_SHELL:-${SHELL##*/}}

if [[ "${BASE_SHELL}" == "zsh" ]]; then
    autoload -Uz +X compinit bashcompinit && compinit && bashcompinit

    zstyle ':completion:*' menu yes select
fi

