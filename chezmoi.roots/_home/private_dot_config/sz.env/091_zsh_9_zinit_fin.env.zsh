#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

if [ -n "$ZI_HOME" ]; then
    autoload -Uz _zi
    (( ${+_comps} )) && _comps[zi]=_zi

    autoload -Uz +X compinit bashcompinit && compinit && bashcompinit
    [[ -n "${DBG}" ]] && echo "zinit/zi loaded available"
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:

