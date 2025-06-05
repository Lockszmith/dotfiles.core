#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

if [ -n "$ZI_HOME" ]; then
    zinit ice depth=1
    zinit light jeffreytse/zsh-vi-mode
else
    znap source jeffreytse/zsh-vi-mode
fi

[[ -n "${DBG}" ]] && echo "jeffreytse/zsh-vi-mode loaded"

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
#
