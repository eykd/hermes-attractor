#!/usr/bin/env bash
#
# create-new-feature.sh — scaffold a new feature branch + spec directory.
#
# Usage:
#   create-new-feature.sh [--json] --short-name <short-name> "<feature description>"
#
# Behaviour:
#   * Fetches remote branches (best-effort) so numbering accounts for remote work.
#   * Finds the highest NNN- prefix across all branches AND specs/ directories.
#   * Assigns the next sequential number (zero-padded to 3 digits).
#   * Creates and checks out the branch "<NNN>-<short-name>".
#   * Creates specs/<NNN>-<short-name>/ and seeds spec.md from the template.
#   * Emits JSON with BRANCH_NAME, SPEC_FILE, FEATURE_NUM when --json is given.
#
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
TEMPLATE="$REPO_ROOT/.specify/templates/spec-template.md"

JSON_OUTPUT=false
SHORT_NAME=""
DESCRIPTION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON_OUTPUT=true; shift ;;
    --short-name) SHORT_NAME="${2:-}"; shift 2 ;;
    --short-name=*) SHORT_NAME="${1#*=}"; shift ;;
    *) DESCRIPTION="$1"; shift ;;
  esac
done

if [[ -z "$SHORT_NAME" ]]; then
  echo "ERROR: --short-name is required" >&2
  exit 1
fi

# Best-effort fetch so numbering is globally unique.
git -C "$REPO_ROOT" fetch --all --prune >/dev/null 2>&1 || true

highest=0
extract_max() {
  # Reads lines, extracts leading NNN- prefixes, tracks the maximum into $highest.
  while IFS= read -r name; do
    if [[ "$name" =~ ([0-9]{3})- ]]; then
      n=$((10#${BASH_REMATCH[1]}))
      (( n > highest )) && highest=$n
    fi
  done
}

# Scan branches (local + remote) and existing specs/ directories.
{ git -C "$REPO_ROOT" branch -a --format='%(refname:short)' 2>/dev/null || true; } | extract_max
if [[ -d "$REPO_ROOT/specs" ]]; then
  { ls -1 "$REPO_ROOT/specs" 2>/dev/null || true; } | extract_max
fi

next=$((highest + 1))
FEATURE_NUM=$(printf '%03d' "$next")
BRANCH_NAME="${FEATURE_NUM}-${SHORT_NAME}"
SPEC_DIR="$REPO_ROOT/specs/$BRANCH_NAME"
SPEC_FILE="$SPEC_DIR/spec.md"

git -C "$REPO_ROOT" checkout -b "$BRANCH_NAME" >/dev/null 2>&1

mkdir -p "$SPEC_DIR"
if [[ -f "$TEMPLATE" ]]; then
  cp "$TEMPLATE" "$SPEC_FILE"
else
  printf '# Feature Specification\n' > "$SPEC_FILE"
fi

if $JSON_OUTPUT; then
  printf '{"BRANCH_NAME":"%s","SPEC_FILE":"%s","FEATURE_NUM":"%s"}\n' \
    "$BRANCH_NAME" "$SPEC_FILE" "$FEATURE_NUM"
else
  echo "BRANCH_NAME: $BRANCH_NAME"
  echo "SPEC_FILE: $SPEC_FILE"
  echo "FEATURE_NUM: $FEATURE_NUM"
fi
