#! /usr/bin/env bash

set -e

# Target directory (new structure with symlinks)
DEST_DIR="${DEST_DIR:-${1}}"

is_cmd() {
    type -p -- "${@}" 2> /dev/null 1> /dev/null
}
if is_cmd chezmoi && [[ -z "$RESET" && -z "$SRC_DIR" && -z "$DEST_DIR" ]]; then
    DEST_DIR="$(chezmoi data | jq -r '.chezmoi.sourceDir | split("/") | last')"
fi

# Source directory (existing structure with files)
SRC_DIR=${SRC_DIR:-_src.posix}

SCRIPT_NAME="${0##*/}"
usage() {
    printf '%s\n' \
        'Assign symlinks acrosss chezmoi platform home-dirs' \
        '' \
        'Usage:' \
        "  [RESET=reset] [FORCE=-f] [SRC_DIR=<alt src dir>] ${SCRIPT_NAME} [<destination_directory>]" \
        '' \
        'Notes: ' \
        '  SRC_DIR assumes _src.posix if empty' \
        '  If `chezmoi` state isn'"'"'t broken, the current chezmoihome dir will be used' \
        '' \
        '  When RESET env var is "reset", <destination_directory> is mandatory, ' \
        '    it will remove any symlink in that directory' \
        '' \
        'Examples:' \
        '  # A complete reset' \
        '  RESET=reset SRC_DIR=_src.all ./symclone.sh _src.posix' \
        '  RESET=reset ./symclone.sh _home.macos' \
        '' \
        '  # Alternative setup' \
        '  RESET=reset SRC_DIR=_src.all ./symclone.sh _home.macos && ./symclone.sh' \
        '' \
        '  # General refresh' \
        '  ./symclone.sh' \
        ''
    exit 1
}
# Check if both arguments are provided
if [[ -z "$SRC_DIR" || -z "$DEST_DIR" || "$1" == '--help' ]]; then
    usage
fi

DEST_DIR="${DEST_DIR:?Must supply dest dir name}"

# Ensure source directory exists
if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: Source directory '$SRC_DIR' does not exist."
    exit 1
fi

# Create destination directory if it does not exist
mkdir -p "$DEST_DIR"

# Find all directories and recreate them in the destination
find "$SRC_DIR" -mindepth 1 -type d | while read -r dir; do
    mkdir -p "$DEST_DIR/${dir#$SRC_DIR/}"
done

# Function to get relative path without realpath or python
relpath() {
    local target=$1
    local base=$2
    local target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")
    local base_abs=$(cd "$base" && pwd)
    local common_part="$base_abs"
    local back=""

    while [[ "${target_abs#$common_part}" == "$target_abs" ]]; do
        common_part=$(dirname "$common_part")
        back="../$back"
    done

    echo "${back}${target_abs#$common_part/}"
}

if [[ -n "$RESET" ]]; then
    [[ "$RESET" != 'reset' ]] \
    && printf 'ERROR: RESET was set incorrectly, value %s is illeagal.\n\n' "$RESET" >&2 \
    && usage
    printf "Removing all symlinks from %s destination..." "${DEST_DIR}" >&2
    find "${DEST_DIR}" -type l -delete
    printf "Done.\n" >&2
fi

# Find all non-dirs (files and symlinks) and create symbolic links in the destination
find "$SRC_DIR" -not -type d | while read -r file; do
    # Determine the relative path for the symlink
    target_file="${file#$SRC_DIR/}"
    target_path="$DEST_DIR/${target_file}"
    remove_target="${target_path%/*}/remove_$(<<<"${target_file##*/}" sed -Ee 's/^(symlink|executable)_//; s/(\.tmpl)$//;')"
    src_relative_path=$(relpath "$file" "$(dirname "$DEST_DIR/$target_file")")

    # Create the symlink with relative path
    SKIP=

    [ -z "$SKIP" ] && [ -e "${remove_target}" ] && SKIP="remove entry found for: %s" || true
    [ -z "$SKIP" ] && [ -L "$target_path" ] && [ -z "$FORCE" ] && SKIP="can't force replace %s" || true
    [ -z "$SKIP" ] && [ -e "$target_path" ] && SKIP="%s exists" || true
    [ -n "$DBG" ] && [ -n "$SKIP" ] && printf "$SKIP\n"  "$target_path" || true
    [ -n "$SKIP" ] || ln ${FORCE} -vs "$src_relative_path" "$target_path" || (set | grep -E '^(?:target|remove|src)_' >&2; false)
done

echo "${SCRIPT_NAME} for '$DEST_DIR' done." >&2

