#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

zinit load 'marlonrichert/zsh-autocomplete'
if false; then
    autoload -Uz +X compinit bashcompinit && compinit && bashcompinit

    zstyle ':completion:*' menu yes select
fi

