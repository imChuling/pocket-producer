#!/usr/bin/env bash
# Build and deploy the backend to Cloud Run with the full, versioned
# configuration. Run from anywhere:
#
#   backend/deploy/deploy.sh            # build image from source and deploy
#   backend/deploy/deploy.sh --config   # re-apply env/scaling only, no rebuild
#
# Env vars come from cloudrun.env.yaml, secrets from Secret Manager, scaling
# from the flags below. Nothing here depends on what the previous revision had.
set -euo pipefail

SERVICE=pocket-producer
REGION=us-central1
PROJECT=pocket-producer-ce3e9
HERE="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$(cd "$HERE/.." && pwd)"

# Conference / demo profile: one warm instance so the first visitor does not
# wait ~60 s for CLAP to load; two instances max to absorb a burst.
MIN_INSTANCES="${MIN_INSTANCES:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"

COMMON=(
  --project "$PROJECT"
  --region "$REGION"
  --memory 4Gi
  --cpu 2
  --no-cpu-throttling
  --cpu-boost
  --concurrency 10
  --timeout 300
  --min-instances "$MIN_INSTANCES"
  --max-instances "$MAX_INSTANCES"
  --env-vars-file "$HERE/cloudrun.env.yaml"
  --update-secrets "MONGODB_CONNECTION_STRING=mongodb-connection-string:latest,VOYAGE_API_KEY=voyage-api-key:latest,GOOGLE_API_KEY=google-api-key:latest,JOB_TRIGGER_SECRET=job-trigger-secret:latest"
)

if [[ "${1:-}" == "--config" ]]; then
  gcloud run services update "$SERVICE" "${COMMON[@]}"
else
  gcloud run deploy "$SERVICE" --source "$BACKEND" "${COMMON[@]}"
fi

echo
echo "Waiting for readiness..."
URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')"
for _ in $(seq 1 30); do
  if body="$(curl -sf --max-time 10 "$URL/ready")"; then
    echo "$body"
    break
  fi
  sleep 5
done
echo "Check logs for 'CLAP warmup complete' and 'role probe warmup complete'."
