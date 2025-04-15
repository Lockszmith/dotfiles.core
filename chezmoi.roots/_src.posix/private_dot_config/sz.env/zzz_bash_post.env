#!/usr/bin/env -S bash -c 'echo "Not a user script. source(aka .) only"'

BASE_SHELL=${BASE_SHELL:-${SHELL##*/}}

if [[ "${BASE_SHELL}" == "bash" ]]; then
    eval "${SZ_ENV_BASH_LOAD_PREEXEC}"
    if [[ -n "${BLE_VERSION-}" ]]; then
        [[ -n "${DBG}" ]] && echo "attaching ble.sh"
        ble-attach
    fi
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
