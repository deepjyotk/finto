#!/bin/bash
# Sync Google Secret Manager from local .env (ground truth).
# Creates/updates each non-empty .env key and grants run-runtime secretAccessor.
set -euo pipefail

PROJECT_ID="finto-477904"
RUNTIME_SA="run-runtime@finto-477904.iam.gserviceaccount.com"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -f ".env" ]; then
  echo "Error: .env file not found"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

# Collect keys from .env (same order as the file). Keep in sync with
# cloudbuild.yaml --set-secrets= and fetch-secrets.sh KNOWN_SECRETS.
SECRETS=()
while IFS= read -r raw || [[ -n "$raw" ]]; do
  [[ "$raw" =~ ^[[:space:]]*# ]] && continue
  t="${raw#"${raw%%[![:space:]]*}"}"
  t="${t%"${t##*[![:space:]]}"}"
  [[ -z "$t" ]] && continue
  t="${t#export }"
  t="${t#"${t%%[![:space:]]*}"}"
  [[ "$t" != *=* ]] && continue
  key="${t%%=*}"
  key="${key#"${key%%[![:space:]]*}"}"
  key="${key%"${key##*[![:space:]]}"}"
  [[ -z "$key" ]] && continue
  SECRETS+=("$key")
done < .env

if ((${#SECRETS[@]} == 0)); then
  echo "Error: no keys found in .env"
  exit 1
fi

echo "Syncing ${#SECRETS[@]} secrets from .env → Secret Manager (${PROJECT_ID})..."

for secret_name in "${SECRETS[@]}"; do
  secret_value="${!secret_name-}"

  if [ -z "$secret_value" ]; then
    echo "Warning: $secret_name is empty in .env, skipping..."
    continue
  fi

  if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
    echo "Updating $secret_name..."
    echo -n "$secret_value" | gcloud secrets versions add "$secret_name" --project="$PROJECT_ID" --data-file=-
  else
    echo "Creating $secret_name..."
    echo -n "$secret_value" | gcloud secrets create "$secret_name" --project="$PROJECT_ID" --replication-policy=automatic --data-file=-
  fi

  # Ensure runtime SA can read every secret, including pre-existing ones.
  gcloud secrets add-iam-policy-binding "$secret_name" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:$RUNTIME_SA" \
    --role=roles/secretmanager.secretAccessor >/dev/null
done

echo "All secrets updated successfully"
