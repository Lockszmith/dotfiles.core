#!/usr/bin/env -S bash -c 'echo "Not a user script. source(aka .) only"'

if [ -f "$SZ_ENV_ROOT/lib/complete-alias" ]; then
    source <(sed -Ee 's/\(\( "\$COMPAL_AUTO_UNMASK"/(( \${COMPAL_AUTO_UNMASK:-0}/g' "$SZ_ENV_ROOT/lib/complete-alias") --noattach
fi

if [[ -n "${DBG}" && -n "$( command -v _complete_alias )" ]]; then
    echo "complete-alias will be loaded."
fi

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
