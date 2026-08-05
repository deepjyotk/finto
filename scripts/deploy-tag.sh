#!/usr/bin/env bash
# Used by: make deploy-tag
# Validates .env keys against update-secrets.sh + cloudbuild.yaml, then creates the next patch semver tag on GitHub via gh API.
set -euo pipefail

REPO="${DEPLOY_TAG_REPO:-deepjyotk/finto}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE=".env"
SECRETS_FILE="update-secrets.sh"
CLOUD_BUILD="cloudbuild.yaml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: $ENV_FILE not found in $ROOT"
  exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "Error: gh (GitHub CLI) is not installed or not on PATH."
  echo "Install it with: brew install gh"
  exit 1
fi
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: not a git repository (run from the finto repo root)"
  exit 1
fi

missing_in_secrets=()
missing_in_cloudbuild=()

trim() {
  # Trim leading/trailing whitespace without external tooling (avoid xargs).
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

while IFS= read -r raw || [[ -n "$raw" ]]; do
  [[ "$raw" =~ ^[[:space:]]*# ]] && continue
  t="$(trim "$raw")"
  [[ -z "$t" ]] && continue
  t="${t#export }"
  t="$(trim "$t")"
  [[ -z "$t" ]] && continue
  [[ "$t" != *=* ]] && continue
  key="$(trim "${t%%=*}")"
  [[ -z "$key" ]] && continue

  if ! grep -Fq "\"$key\"" "$SECRETS_FILE"; then
    missing_in_secrets+=("$key")
  fi
  if ! grep -Fq -- "--set-secrets=${key}=" "$CLOUD_BUILD"; then
    missing_in_cloudbuild+=("$key")
  fi
done < "$ENV_FILE"

had_issue=0
if ((${#missing_in_secrets[@]})); then
  had_issue=1
  echo "The following .env keys are missing from $SECRETS_FILE (SECRETS array):"
  printf '  - %s\n' "${missing_in_secrets[@]}"
  echo
fi
if ((${#missing_in_cloudbuild[@]})); then
  had_issue=1
  echo "The following .env keys are missing from $CLOUD_BUILD (--set-secrets=...):"
  printf '  - %s\n' "${missing_in_cloudbuild[@]}"
  echo
fi
if ((had_issue)); then
  echo "Fix the above before tagging. Aborting."
  exit 1
fi

echo "All .env keys are present in $SECRETS_FILE and $CLOUD_BUILD."

if ! tags_out="$(gh api "repos/${REPO}/tags" --paginate -q '.[].name')"; then
  echo "Error: failed to list tags for ${REPO}. Run: gh auth login"
  exit 1
fi
latest="$(echo "$tags_out" | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n1 || true)"

if [[ -z "$latest" ]]; then
  echo "No existing semver tags like v0.0.0 found on github.com/${REPO}; defaulting next tag to v0.0.1"
  new_tag="v0.0.1"
else
  ver="${latest#v}"
  IFS=. read -r major minor patch <<<"$ver"
  major=$((10#${major:-0}))
  minor=$((10#${minor:-0}))
  patch=$((10#${patch:-0} + 1))
  new_tag="v${major}.${minor}.${patch}"
  echo "Latest semver tag on ${REPO}: ${latest} -> new tag: ${new_tag}"
fi

sha="$(git rev-parse HEAD)"
echo "Tagging commit ${sha} as ${new_tag} on GitHub (${REPO})..."

gh api --method POST "repos/${REPO}/git/refs" \
  -f "ref=refs/tags/${new_tag}" \
  -f "sha=${sha}"

echo "Created and published tag ${new_tag} (refs/tags on GitHub)."
