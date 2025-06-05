#!/usr/bin/env -S zsh -c 'echo "Not a user script. source(aka .) only"'

if [ -n "$ZI_HOME" ]; then
    zinit light 'marlonrichert/zsh-autocomplete'
    zinit light 'zsh-users/zsh-autosuggestions'
else
    znap source 'marlonrichert/zsh-autocomplete'
    znap source 'zsh-users/zsh-autosuggestions'

    # Make Tab and ShiftTab cycle completions on the command line
    # bindkey              '^I'         menu-complete
    # bindkey "$terminfo[kcbt]" reverse-menu-complete

    # Make Tab and ShiftTab go to the menu
    bindkey              '^I' menu-select
    bindkey "$terminfo[kcbt]" menu-select

    # Make Tab and ShiftTab change the selection in the menu
    bindkey -M menuselect              '^I'         menu-complete
    bindkey -M menuselect "$terminfo[kcbt]" reverse-menu-complete

    # Make ← and → always move the cursor on the command line
    # bindkey -M menuselect  '^[[D' .backward-char  '^[OD' .backward-char
    # bindkey -M menuselect  '^[[C'  .forward-char  '^[OC'  .forward-char

    # `znap install` adds new commands and completions.
    znap install aureliojargas/clitest zsh-users/zsh-completions zdharma-continuum/fast-syntax-highlighting
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:

