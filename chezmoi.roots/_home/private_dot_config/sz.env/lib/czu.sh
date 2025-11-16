#!/usr/bin/env -S bash -c 'echo "Not a user script. source(aka .) only"'
# shellcheck disable=SC1090

# This entire code is evaluated inside czu() function from ~/.config/sz.env/981_chezmoi.env
local bin=0 all=0 eza=0 init=1 refresh=1 interact='--less-interactive' verbose='' debug='' prompts='--promptDefaults'
while [[ $# -gt 0 ]]; do
    case "$1" in
        '--bin') bin=1 ;;
        '--no-bin') bin=1 ;;
        '--no-init') init=0 ;;
        '--reinit') prompts='' ;;
        '--all') all=1; bin=1; eza=1 ;;
        '--eza') eza=1 ;;
        '--no-eza') eza=0 ;;
        '--no-refresh') refresh=0 ;;
        '--yes') interact='' ;;
        '--quiet') verbose='' ;;
        '--verbose') verbose='--verbose' ;;
        '--debug') debug='--debug' ;;
        '--help') printf '%s\n' \
            'Usage:' \
            '  czu ' \
            '  czu [--help]' \
            '  czu [--no-init] [[--bin | --all [--no-bin]] [--eza | --no-eza]] ' \
            '      [--yes] [--reinit] [--no-refresh] [--quiet] [--debug]' \
            '' \
            'Description:' \
            #123456789012345678901234567890123456789012345678901234567890123456789012
            '  czu is a helper function for updating your chezmoi managed home dir' \
            '  the steps are:' \
            "    upgrade chezmoi's binary      # --bin/--no-bin" \
            '    reapply config.toml (init)    # --no-init to skip' \
            '                                  # reuse defaults unless --reinit' \
            '    exclude or include externals  # --all to include' \
            '      include or exclude eza binary # --eza / --no-eza' \
            '      refresh externals cache       # --no-refresh to skip' \
            '' \
            'More arguments:' \
            '  --yes' \
            '  --quiet' \
            '  --debug' \
            '  --help' \
            ''
            return 1
            ;;
    esac
    shift
done
if [[ $bin -eq 1 ]]; then
    env chezmoi upgrade
fi
env chezmoi git -- pull --autostash --rebase \
&& env chezmoi init $prompts $verbose $debug \
&& env chezmoi status $verbose $debug

CZ_EXTR_SAVE="$CZ_EXTR"
unset CZ_EXTR
if [[ $all -eq 1 ]]; then
    export CZ_EXTR=1 IGNORE_EZA=1
    if [[ $eza -eq 1 ]]; then
        unset IGNORE_EZA
        export CZ_EXTR=1
        CZ_EZA_PREFIX="" \
        env chezmoi status --include externals $debug $HOME/.local/bin/eza \
            || (CZ_EZA_PREFIX='./' chezmoi status --include externals $debug $HOME/.local/bin/eza )
    else
        env chezmoi status --include externals $debug
    fi

    echo Applying External changes...
    env chezmoi apply --interactive --include externals $verbose $debug
fi
echo Applying pending changes...
env chezmoi apply --less-interactive --verbose $verbose $debug

export CZ_EXTR="$CZ_EXTR_SAVE"
unset CZ_EXTR_SAVE

[[ $refresh -ne 1 ]] || (printf "restarting shell...\n" >&2 && false ) || exec $SHELL -l
