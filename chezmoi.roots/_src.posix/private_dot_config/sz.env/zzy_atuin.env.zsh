#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

if is_cmd atuin; then

    # . <( atuin init "${BASE_SHELL}" )
    zinit light atuinsh/atuin

    [[ -n "${DBG}" ]] && echo "atuin loaded."
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
