#!/bin/bash
set -e

PROJECT_ID="finto-477904"
RUNTIME_SA="run-runtime@finto-477904.iam.gserviceaccount.com"

if [ ! -f ".env" ]; then
  echo "Error: .env file not found"
  exit 1
fi

set -a
source .env
set +a

SECRETS=(
  "SECRET_KEY"
  "DATABASE_URL"
  "OPENAI_API_KEY"
  "TAVILY_API_KEY"
  "WA_APP_SECRET"
  "WA_VERIFY_TOKEN"
  "WA_PHONE_NUMBER_ID"
  "WA_USER_OR_SYSTEM_TOKEN"
  "WA_SENDER_E164"
  "LANGSMITH_TRACING"
  "LANGSMITH_ENDPOINT"
  "LANGSMITH_API_KEY"
  "LANGSMITH_PROJECT"
  "PINECONE_API_KEY"
  "THESYS_API_KEY"
  "THESYS_ENABLED"
  "THESYS_BASE_URL"
  "THESYS_MODEL"
  "ROUTER_MODEL"
  "PORTFOLIO_MODEL"
  "NEWS_MODEL"
  "SENDGRID_API_KEY"
  "SENDGRID_FROM_EMAIL"
  SENDGRID_FROM_NAME
)

for secret_name in "${SECRETS[@]}"; do
  secret_value="${!secret_name}"
  
  if [ -z "$secret_value" ]; then
    echo "Warning: $secret_name is empty in .env, skipping..."
    continue
  fi
  
  if gcloud secrets describe "$secret_name" --project=$PROJECT_ID &>/dev/null; then
    echo "Updating $secret_name..."
    echo -n "$secret_value" | gcloud secrets versions add "$secret_name" --project=$PROJECT_ID --data-file=-
  else
    echo "Creating $secret_name..."
    echo -n "$secret_value" | gcloud secrets create "$secret_name" --project=$PROJECT_ID --replication-policy=automatic --data-file=-
    gcloud secrets add-iam-policy-binding "$secret_name" --project=$PROJECT_ID --member=serviceAccount:$RUNTIME_SA --role=roles/secretmanager.secretAccessor
  fi
done

echo "All secrets updated successfully"