#! /usr/bin/env sh
set -e

SCRIPT_DIR=${SCRIPT_DIR:-"$( cd -- "$( dirname -- "$0" )" &> /dev/null && pwd )"}

SRC=${1:-$(cd $SCRIPT_DIR/../.. && pwd)}
printf 'SRC=%s\n' "$SRC"
[ "$SRC" = ":" ] || cd $SRC
(
    cd "${2:-${HOME}}"
    echo cleanup, phase 1...
    find -P . -mindepth 1 -maxdepth 1 -type f \
        -name '.zsh_history' -or \
        -name '.gitconfig' -or \
        -name '.bash_history' -or \
        -name '.zsh_history' \
	-print -delete

    echo cleanup, phase 2...
    find . -mindepth 1 -maxdepth 2 -type l -print -delete
    mkdir -p .config

    [ "$SRC" != ":" ] || exit 99
    echo linking...
    (
        cd $SRC; (
            find .       -mindepth 1 -maxdepth 1 -not -path './.config' -not -path './Dockerfile'
            find .config -mindepth 1 -maxdepth 1 -not -path '*/chezmoi' -not -path '*/zellij'     -not -path '*/starship*'
        )
    ) | xargs -rtI '{}' ln -sr $SRC'/{}' '{}' | true
)
echo done

