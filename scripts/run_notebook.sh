#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
notebook="${1:-nodebooks/split_text.ipynb}"

if [[ "$notebook" != /* ]]; then
    notebook="$repo_root/$notebook"
fi

if [[ ! -f "$notebook" ]]; then
    printf 'Notebook not found: %s\n' "$notebook" >&2
    exit 1
fi

cd "$repo_root"
exec uv run --with notebook jupyter notebook "$notebook"
