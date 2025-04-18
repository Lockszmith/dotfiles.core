#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

zinit ice depth=1
zinit light jeffreytse/zsh-vi-mode

[[ -n "${DBG}" ]] && echo "jeffreytse/zsh-vi-mode loaded"

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
#
