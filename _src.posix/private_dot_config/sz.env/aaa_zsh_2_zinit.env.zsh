#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

#""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
#"""                              z-shell/zi                                  """
#""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
#
# ### Added by z-shell/zi's installer
ZI_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zi/bin"
mkdir -p "$(dirname "$ZI_HOME")"
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
autoload -Uz _zi
(( ${+_comps} )) && _comps[zi]=_zi
# examples here -> https://wiki.zshell.dev/ecosystem/category/-annexes
zicompinit # <- https://wiki.zshell.dev/docs/guides/commands
### End of z-shell/zi installer's chunk
alias zinit=zi

[[ -n "${DBG}" ]] && echo "zi ready"

