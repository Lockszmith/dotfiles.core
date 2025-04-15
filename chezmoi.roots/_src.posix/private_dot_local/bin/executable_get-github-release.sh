#! /usr/bin/env bash

GH_PROJECT="${1}"
GH_DL_TAG="${2:-latest}"
GH_FILTER="${3:-deb}"
if [[ ! "$GH_FILTER" =~ '(' ]]; then
    GH_FILTER="contains(\"${GH_FILTER}\")"
fi
SRC_URL=https://api.github.com/repos/${GH_PROJECT}/releases/${GH_DL_TAG}
DL_URL=$( \
    curl -sL curl ${SRC_URL} \
        | jq -r " \
            .assets[] \
            | select(.browser_download_url \
                | ${GH_FILTER} ) \
            | .browser_download_url \
        ")
[[ -n "$DL_URL" ]] \
    && printf "%s\n" $DL_URL \
    || return 1 2>/dev/null || exit 1

# vim: set ft=sh expandtab tabstop=4 shiftwidth=4:
