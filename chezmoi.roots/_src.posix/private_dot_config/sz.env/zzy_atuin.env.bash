#!/usr/bin/env -S bash -c 'echo "Not a user script. source(aka .) only"'

if is_cmd atuin; then
    if ! [[ -n "$SZ_ENV_BASH_LOAD_PREEXEC$BLE_VERSION" ]]; then
        printf '%s\n' \
            'atuin was found, but bash-preexec or ble.sh are not loaded,' \
            'to load atuin, first run update-ble.sh or update-bash-preexec ' \
            'then relaod (_r) the shell.'
    fi

    . <( atuin init bash )
    . <( atuin gen-completions --shell bash )

    [[ -n "${DBG}" ]] && echo "atuin loaded."
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
