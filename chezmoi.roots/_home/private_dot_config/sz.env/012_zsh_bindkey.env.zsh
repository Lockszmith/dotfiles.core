#!/usr/bin/env -S bash -c 'echo "Not a user script. source(aka .) only"'

# Auto-detect via terminfo (works for most terminals)
typeset -A key
key[Home]="${terminfo[khome]}"
key[End]="${terminfo[kend]}"
[[ -n "${key[Home]}" ]] && bindkey "${key[Home]}" beginning-of-line
[[ -n "${key[End]}"  ]] && bindkey "${key[End]}" end-of-line

if [[ -n "${DBG}" ]]; then
    echo "bindkey setup complete."
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:

