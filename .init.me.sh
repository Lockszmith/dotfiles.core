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

# Make sure temporary directory exists
CZ_SCRIPT_TEMPDIR="${CZ_SCRIPT_TEMPDIR:-~/.cache/chezmoi/tmp}"
mkdir -p "${CZ_SCRIPT_TEMPDIR}"

# (in debug x2 mode) Show the existing configuration before destroying it
[[ -z "${CZ_DEBUG}" ]] || chezmoi cat-config

# Destroy existing chezmoi state
rm -fR ~/.config/chezmoi ~/.local/share/chezmoi/.chezmoiroot

# Create a temporary chezmoi configuration bypass /tmp noexec situation
mkdir -p ~/.config/chezmoi
cat - > ~/.config/chezmoi/chezmoi.toml <<TOML
scriptTempDir="${CZ_SCRIPT_TEMPDIR}"
TOML

# Show the initial configuration in debug x2 mode
[[ -z "${CZ_DEBUG}" ]] || chezmoi cat-config

# "It's show time!" - Re-initialize
chezmoi init ${CZ_DEBUG} --apply
unset SET_X

# Show the final configuration in debug x2 mode
[[ -z "${CZ_DEBUG}" ]] || chezmoi cat-config
