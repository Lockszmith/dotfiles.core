#! /usr/bin/env bash

# Helper function
is_sourced() {
    if [ -n "$ZSH_VERSION" ]; then 
        case $ZSH_EVAL_CONTEXT in *:file:*) return 0;; esac
    else  # Add additional POSIX-compatible shell names here, if needed.
        case ${0##*/} in dash|-dash|bash|-bash|ksh|-ksh|sh|-sh) return 0;; esac
    fi
    return 1; # NOT sourced.
}

BASE_0=${BASE_0:-$0}
BASE_SHELL=$(basename "$SHELL")

is_cmd() {
type -- "${@}" 2> /dev/null 1> /dev/null
}

if is_sourced; then
    # shellcheck disable=SC2139 # This expands when defined, not when used.
    alias _r="unset DBG; exec $SHELL -l "
    # shellcheck disable=SC2139 # This expands when defined, not when used.
    alias _rdbg="exec sh -c 'DBG=1 $SHELL -l '"

    SZ_ENV_ROOT=$( cd -- "$( dirname -- "${BASE_0}" )" &> /dev/null && pwd )
    USER_HOME=$HOME
    [[ -n "${SUDO_USER}" ]] && USER_HOME="$(eval "echo ~${SUDO_USER}")"

    load_next() {
        [ "$LOAD_EXIT" != "0" ] && return 1

        if [[ -n "${DBG}" ]]; then
            echo "Loading ${1}..." 1>&2
            #shellcheck disable=SC2086
            ${DBG/%1/:} 1>&2
        fi
        #shellcheck source=/dev/null
        . "${1}"
    }
    
    load_all() {
        local ALL_ENV_FILES
        if [ -z "$SZ_ENV_LOADED" ]; then
            SZ_ENV_LOADED=1
            LOAD_EXIT=0

            # The following constructs a list of load_next ... commands
            ALL_ENV_FILES="$(
                find ~/.config/sz.env -xdev -type d -not -name '*.off' \
                    -exec sh -c '
                        find "$1" -xdev -maxdepth 1 -type f -name "ID_*.env" | sort
                    ' shell '{}' ';' \
                    -exec sh -c '
                        find "$1" -xdev -maxdepth 1 -type f -name "PATH_*.env" | sort
                    ' shell '{}' ';' \
                    -exec sh -c '
                        find "$1" -xdev -maxdepth 1 -type f -name "*.env" -not -name "ID_*" -not -name "PATH_*" -print | sort
                    ' shell '{}' ';' \
                | sed -e 's/^/load_next "/; s/$/";/'
            )"
            if [ -n "$DBG_NO_SZ_LOAD" ]; then
               ALL_ENV_FILES=$(<<<"$ALL_ENV_FILES" sed -Ee '
                   /PATH_/!s/^(load_next )/# \1/
               ')
	       printf 'Loading limited environment...\n'
            fi
            # Run the constructed (see above) list
            eval "$ALL_ENV_FILES"
        fi
    }
    load_all
elif [[ "$1" == '-' ]]; then
    echo "BASE_0=${BASE_0}"
    cat "${0}"
else
    is_cmd "${BASE_0##*/}" && SCRIPT_NAME="${BASE_0##*/}" || SCRIPT_NAME="${BASE_0/$HOME/\~}"
    printf '%s\n' \
        "It seems '$SCRIPT_NAME' was invoked as a standalone script." \
        'This script is designed to produce output that is sourced.' \
        '' \
        'The recommended way is to use calling pattern below:' \
        "    $ . <( $SCRIPT_NAME - ) # Note the '-' after the script's name" \
        ''
fi

