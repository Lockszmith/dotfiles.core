#!/usr/bin/env -S bash -c 'echo "Not a user script. source(aka .) only"'
# shellcheck disable=SC1090

# This entire code is evaluated inside czu() function from ~/.config/sz.env/981_chezmoi.env
local bin=0 all=0 init=1 refresh=1 interact='--less-interactive' verbose='' debug='' CZ_RECONFIG='' CZ_RECONFIG_FLAGS=''
while [[ $# -gt 0 ]]; do
    case "$1" in
        '--bin') bin=1 ;;
        '--no-bin') bin=1 ;;
        '--no-init') init=0 ;;
        '--reinit') CZ_RECONFIG_FLAGS=1 ;;
        '--reinit=all') CZ_RECONFIG=1 ;;
        '--all') all=1; bin=1 ;;
        '--no-refresh') refresh=0 ;;
        '--yes') interact='' ;;
        '--quiet') verbose='' ;;
        '--verbose') verbose='--verbose' ;;
        '--debug') debug='--debug' ;;
        '--help') printf '%s\n' \
            'Usage:' \
            '  czu ' \
            '  czu [--help]' \
            '  czu [--no-init] [[--bin | --all [--no-bin]]] ' \
            '      [--yes] [--reinit[=all]] [--no-refresh] [--quiet] [--debug]' \
            '' \
            'Description:' \
            #123456789012345678901234567890123456789012345678901234567890123456789012
            '  czu is a helper function for updating your chezmoi managed home dir' \
            '  the steps are:' \
            "    upgrade chezmoi's binary      # --bin/--no-bin" \
            '    reapply config.toml (init)    # --no-init to skip' \
            '      will prompt for new values  # --reinit will force prompt(s)' \
            '    exclude or include externals  # --all to include' \
            '      refresh externals cache     # --no-refresh to skip' \
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
&& CZ_RECONFIG="$CZ_RECONFIG" CZ_RECONFIG_FLAGS="$CZ_RECONFIG_FLAGS" env chezmoi init $verbose $debug \
&& env chezmoi status $verbose $debug

CZ_EXTR_SAVE="$CZ_EXTR"
unset CZ_EXTR
if [[ $all -eq 1 ]]; then
    export CZ_EXTR=1
    env chezmoi status --include externals $debug

    echo Applying External changes...
    PAGER="$CZ_PAGER" env chezmoi apply --interactive --include externals $verbose $debug
    cz-get-all-files refresh-cache > /dev/null
fi
export CZ_EXTR="$CZ_EXTR_SAVE"
unset CZ_EXTR_SAVE

echo Applying pending changes...
PAGER="$CZ_PAGER" env chezmoi apply --less-interactive $verbose $debug

[[ $refresh -ne 1 ]] || (printf "restarting shell...\n" >&2 && false ) || exec $SHELL -l
