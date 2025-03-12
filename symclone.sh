#! /usr/bin/env bash

set -e

# Source directory (existing structure with files)
SRC_DIR=_src.posix

# Target directory (new structure with symlinks)
DEST_DIR="${1}"

is_cmd() {
    type -p -- "${@}" 2> /dev/null 1> /dev/null
}
if is_cmd chezmoi && [ -z "$DEST_DIR" ]; then
    DEST_DIR="$(chezmoi data | jq -r '.chezmoi.sourceDir | split("/") | last')"
fi
DEST_DIR="${DEST_DIR:?Must supply dest dir name}"

# Check if both arguments are provided
if [[ -z "$SRC_DIR" || -z "$DEST_DIR" ]]; then
    echo "Usage: $0 <source_directory> <destination_directory>"
    exit 1
fi

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

# Find all files and create symbolic links in the destination
find "$SRC_DIR" -type f | while read -r file; do
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

echo "Symbolic links created successfully in '$DEST_DIR'."
