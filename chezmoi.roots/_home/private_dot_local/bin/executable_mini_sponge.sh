#!/bin/bash
# mini-sponge: Drop-in sponge replacement (no deps).
# Reads stdin to temp file (mktemp), atomically mv's to file.
# Usage: command | ./mini-sponge <filename>
# Preserves perms/owner. Safe for huge files.

set -euo pipefail  # Strict mode: fail fast

if [ $# -ne 1 ]; then
    cat >&2 <<EOF
Usage: command | mini-sponge <filename>

Examples:
  jq '.foo=1' file.json | mini-sponge file.json
  sed 's/old/new/' file.txt | mini-sponge file.txt

EOF
    exit 1
fi

filename="$1"
tempfile=$(mktemp --dry-run --suffix="${filename##*/}.tmp.$$") || {
    echo "mini-sponge: mktemp failed" >&2
    exit 1
}

# Read stdin to temp
if ! cat > "$tempfile" 2>/dev/null; then
    rm -f "$tempfile"
    echo "mini-sponge: stdin read failed" >&2
    exit 1
fi

# Atomic mv (preserves perms/owner)
mv "$tempfile" "$filename" || {
    rm -f "$tempfile"
    echo "mini-sponge: mv to '$filename' failed" >&2
    exit 1
}
