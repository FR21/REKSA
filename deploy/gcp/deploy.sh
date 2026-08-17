#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${GCP_PROJECT_ID:-}" ]]; then
  read -r -p "Google Cloud/Firebase Project ID: " GCP_PROJECT_ID
  export GCP_PROJECT_ID
fi
if [[ ! "${GCP_PROJECT_ID}" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]]; then
  echo "ERROR: Google Cloud Project ID tidak valid: ${GCP_PROJECT_ID}"
  exit 1
fi
GCP_REGION="${GCP_REGION:-asia-southeast2}"
PUBSUB_TOPIC="${PUBSUB_TOPIC:-reksa-telemetry}"
PUBSUB_SUBSCRIPTION="${PUBSUB_SUBSCRIPTION:-reksa-cloud-run-push}"
AI_SERVICE="${AI_SERVICE:-reksa-ai}"
BACKEND_SERVICE="${BACKEND_SERVICE:-reksa-backend}"
RUNTIME_SA="reksa-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
PUSH_SA="reksa-pubsub-push@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
BRIDGE_SA="reksa-bridge@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

command -v gcloud >/dev/null
command -v npm >/dev/null
if command -v firebase >/dev/null 2>&1; then
  FIREBASE_CMD=(firebase)
else
  command -v npx >/dev/null
  FIREBASE_CMD=(npx --yes firebase-tools@latest)
fi

echo "Project : ${GCP_PROJECT_ID}"
echo "Region  : ${GCP_REGION}"
read -r -p "Ketik PROJECT ID sekali lagi untuk melanjutkan deploy: " CONFIRM_PROJECT_ID
if [[ "${CONFIRM_PROJECT_ID}" != "${GCP_PROJECT_ID}" ]]; then
  echo "Deploy dibatalkan: konfirmasi project tidak sama."
  exit 1
fi

gcloud config set project "${GCP_PROJECT_ID}"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com pubsub.googleapis.com firestore.googleapis.com

gcloud iam service-accounts describe "${RUNTIME_SA}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create reksa-runtime --display-name="REKSA Cloud Run runtime"
gcloud iam service-accounts describe "${PUSH_SA}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create reksa-pubsub-push --display-name="REKSA Pub/Sub push"
gcloud iam service-accounts describe "${BRIDGE_SA}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create reksa-bridge --display-name="REKSA gateway bridge"
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" --member="serviceAccount:${RUNTIME_SA}" --role="roles/datastore.user" >/dev/null

gcloud pubsub topics describe "${PUBSUB_TOPIC}" >/dev/null 2>&1 || gcloud pubsub topics create "${PUBSUB_TOPIC}"
gcloud pubsub topics add-iam-policy-binding "${PUBSUB_TOPIC}" \
  --member="serviceAccount:${BRIDGE_SA}" --role="roles/pubsub.publisher" >/dev/null
gcloud firestore databases describe --database='(default)' >/dev/null 2>&1 || \
  gcloud firestore databases create --database='(default)' --location="${GCP_REGION}" --edition=standard --type=firestore-native

if gcloud run services describe "${AI_SERVICE}" --region "${GCP_REGION}" >/dev/null 2>&1 && \
   [[ "${REDEPLOY_AI:-false}" != "true" ]]; then
  echo "AI service sudah tersedia; melewati build ulang (set REDEPLOY_AI=true untuk memaksa)."
else
  gcloud run deploy "${AI_SERVICE}" \
    --source AI \
    --region "${GCP_REGION}" \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 2 \
    --set-env-vars="REKSA_FORECAST_MODEL=/app/models/near_miss_forecaster.joblib,REKSA_PRIORITY_MODEL=/app/models/priority_engine.joblib"
fi
AI_URL="$(gcloud run services describe "${AI_SERVICE}" --region "${GCP_REGION}" --format='value(status.url)')"

CORS_ORIGINS="https://${GCP_PROJECT_ID}.web.app"
BACKEND_LATEST_CREATED="$(gcloud run services describe "${BACKEND_SERVICE}" --region "${GCP_REGION}" --format='value(status.latestCreatedRevisionName)' 2>/dev/null || true)"
BACKEND_LATEST_READY="$(gcloud run services describe "${BACKEND_SERVICE}" --region "${GCP_REGION}" --format='value(status.latestReadyRevisionName)' 2>/dev/null || true)"
if [[ -n "${BACKEND_LATEST_READY}" && "${BACKEND_LATEST_CREATED}" == "${BACKEND_LATEST_READY}" && \
      "${REDEPLOY_BACKEND:-false}" != "true" ]]; then
  echo "Backend service sudah siap; melewati build ulang (set REDEPLOY_BACKEND=true untuk memaksa)."
else
  gcloud run deploy "${BACKEND_SERVICE}" \
    --source backend \
    --region "${GCP_REGION}" \
    --allow-unauthenticated \
    --service-account "${RUNTIME_SA}" \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 1 \
    --set-env-vars="APP_ENV=cloud,MQTT_ENABLED=false,AI_SERVICE_URL=${AI_URL},DATABASE_URL=sqlite:////tmp/reksa.db,FIRESTORE_ENABLED=true,GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID},CORS_ORIGINS=${CORS_ORIGINS}"
fi
BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" --region "${GCP_REGION}" --format='value(status.url)')"

gcloud run services add-iam-policy-binding "${BACKEND_SERVICE}" \
  --region "${GCP_REGION}" \
  --member="serviceAccount:${PUSH_SA}" \
  --role="roles/run.invoker" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)')"
PUBSUB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
gcloud beta services identity create \
  --service=pubsub.googleapis.com \
  --project="${GCP_PROJECT_ID}" >/dev/null

# The Google-managed identity can take a few seconds to become a valid IAM
# principal. Scope token creation to the push identity instead of the project.
TOKEN_ROLE_BOUND=false
for ATTEMPT in $(seq 1 12); do
  if TOKEN_ROLE_OUTPUT="$(gcloud iam service-accounts add-iam-policy-binding "${PUSH_SA}" \
      --member="serviceAccount:${PUBSUB_SERVICE_AGENT}" \
      --role="roles/iam.serviceAccountTokenCreator" 2>&1)"; then
    TOKEN_ROLE_BOUND=true
    break
  fi
  if [[ "${ATTEMPT}" -lt 12 ]]; then
    echo "Menunggu propagasi Pub/Sub service agent (${ATTEMPT}/12)..."
    sleep 5
  fi
done
if [[ "${TOKEN_ROLE_BOUND}" != "true" ]]; then
  echo "ERROR: gagal memasang izin token Pub/Sub setelah 12 percobaan."
  echo "${TOKEN_ROLE_OUTPUT}"
  exit 1
fi
echo "Izin token Pub/Sub terpasang pada ${PUSH_SA}."

if gcloud pubsub subscriptions describe "${PUBSUB_SUBSCRIPTION}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "${PUBSUB_SUBSCRIPTION}" \
    --push-endpoint="${BACKEND_URL}/api/v1/ingest/pubsub" \
    --push-auth-service-account="${PUSH_SA}"
else
  gcloud pubsub subscriptions create "${PUBSUB_SUBSCRIPTION}" \
    --topic="${PUBSUB_TOPIC}" \
    --push-endpoint="${BACKEND_URL}/api/v1/ingest/pubsub" \
    --push-auth-service-account="${PUSH_SA}" \
    --ack-deadline=30
fi

npm --prefix frontend ci
VITE_API_URL="${BACKEND_URL}/api/v1" VITE_WS_URL="${BACKEND_URL/https:/wss:}/ws/live" npm --prefix frontend run build
"${FIREBASE_CMD[@]}" deploy --only hosting --project "${GCP_PROJECT_ID}"

echo "REKSA deployment complete"
echo "Dashboard: https://${GCP_PROJECT_ID}.web.app"
echo "Backend:   ${BACKEND_URL}"
echo "AI:        ${AI_URL}"
echo "Configure bridge/.env with GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID} and PUBSUB_TOPIC=${PUBSUB_TOPIC}"
echo "Bridge service account: ${BRIDGE_SA}"
