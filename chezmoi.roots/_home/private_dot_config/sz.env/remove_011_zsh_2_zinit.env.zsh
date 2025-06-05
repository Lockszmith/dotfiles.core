#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

#""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
#"""                              z-shell/zi                                  """
#""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
#
# ### Added by z-shell/zi's installer
ZI_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zi"
mkdir -p "$(dirname "$ZI_HOME")"

typeset -gAH ZINIT=(HOME_DIR "${ZI_HOME}" COMPINIT_OPTS '-D -i -u -C -w')

if [[ ! -d "$ZI_HOME/.git" ]]; then
    print -P "%F{33}▓▒░ %F{160}Installing (%F{33}z-shell/zi%F{160})…%f"
    command mkdir -p "$(dirname "$ZINIT_HOME")" \
        && command chmod go-rwX "$(dirname "$ZI_HOME")"
    command git clone -q --depth=1 --branch "main" \
        https://github.com/z-shell/zi.git "$ZI_HOME" \
        && print -P "%F{33}▓▒░ %F{34}Installation successful.%f%b" \
        || print -P "%F{160}▓▒░ The clone has failed.%f%b"
fi
source "${ZI_HOME}/zi.zsh"
# examples here -> https://wiki.zshell.dev/ecosystem/category/-annexes
zicompinit # <- https://wiki.zshell.dev/docs/guides/commands
### End of z-shell/zi installer's chunk
alias zinit=zi

autoload -Uz _zi
(( ${+_comps} )) && _comps[zi]=_zi

[[ -n "${DBG}" ]] && echo "zinit/zi initialized"

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:

