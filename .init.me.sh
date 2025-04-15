#! /usr/bin/env bash

CZ_DEBUG=
while true; do
    case "$1" in
        --init) break;;
        --debug) [[ -z "$SET_X" ]] && export SET_X=set || CZ_DEBUG=--debug;;
        *)  printf '%s\n' \
                'Re-initialize chezmoi based environment, reloading it from source' \
                '' \
                'Usage:' \
                "  ${0##*/} [--init]" \
                '' \
                'Arguments:' \
                '  without any (or unknown) arguments, displays this usage message.' \
                '' \
                '  --init    Perform initialization' \
                '' \
                'Description:' \
                '  Deletes ~/.config/chezmoi and the .chezmoiroot and performs' \
                '    chezmoi init --apply' \
                '  This, in effect, will trigger .chezmoiscripts/run_init.sh template' \
                '' \
                '  the init script template determins the type of OS and hardware we are' \
                '  running on and assigns (creates a symlink) the proper root to' \
                '  .chezmoiroot at which point, it re-initializes the local chezmoi' \
                ''
            exit 2
            ;;
    esac
    shift
done

set -e
${SET_X:-:} -x

rm -fR ~/.config/chezmoi ~/.local/share/chezmoi/.chezmoiroot
chezmoi init ${CZ_DEBUG} --apply
unset SET_X
