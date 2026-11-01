#!/usr/bin/env bash
# Maintainers: copy the canonical tooling files (tooling/) into every dharma_* checkout.
#
#   scripts/sync_tooling.sh [--check] [checkout ...]   (default: every src/**/dharma_* repository)
#
# Copies ruff.toml, .clang-format, .editorconfig, .prettierrc.yaml, .pre-commit-config.yaml and
# .gitignore to the repository root and ci-package.yml to .github/workflows/ci.yml. --check only
# lists the files that differ (exit 1 when any does). Commit the result in each repository.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLING="$ROOT/tooling"
FILES=(ruff.toml .clang-format .editorconfig .prettierrc.yaml .pre-commit-config.yaml .gitignore)
CHECK=0
if [[ "${1:-}" == "--check" ]]; then
    CHECK=1
    shift
fi
REPOS=("$@")
if [[ ${#REPOS[@]} -eq 0 ]]; then
    while IFS= read -r git_dir; do
        REPOS+=("$(dirname "$git_dir")")
    done < <(find "$ROOT/src" -maxdepth 3 -type d -name .git -path '*/dharma_*/.git' | sort)
fi
[[ ${#REPOS[@]} -gt 0 ]] || { echo "no dharma_* checkouts under src/ (scripts/dev.sh import)" >&2; exit 1; }

differ=0
sync() { # sync <source> <destination>
    if cmp -s "$1" "$2"; then
        return 0
    fi
    if [[ $CHECK -eq 1 ]]; then
        echo "differs: $2"
        differ=1
    else
        mkdir -p "$(dirname "$2")"
        cp "$1" "$2"
        echo "updated: $2"
    fi
}

for repo in "${REPOS[@]}"; do
    [[ -d "$repo/.git" ]] || { echo "not a git checkout: $repo" >&2; exit 1; }
    for file in "${FILES[@]}"; do
        sync "$TOOLING/$file" "$repo/$file"
    done
    sync "$TOOLING/ci-package.yml" "$repo/.github/workflows/ci.yml"
done
exit $differ
