#!/usr/bin/env bash
# deploy.sh — Build, deploy to Cloud Run, and reset Telegram webhook.
#
# Usage:
#   ./deploy.sh            # full deploy + webhook
#   ./deploy.sh --no-hook  # deploy only, skip webhook reset
set -euo pipefail

PROJECT="my-budget-bot-486112"
SERVICE="my-budget-bot"
REGION="us-central1"

# ── Preflight ────────────────────────────────────────────────────────
echo "==> Checking gcloud auth..."
gcloud auth print-access-token > /dev/null 2>&1 || {
  echo "ERROR: Not authenticated. Run: gcloud auth login"; exit 1
}
gcloud config set project "$PROJECT" --quiet

# ── Run tests ────────────────────────────────────────────────────────
echo "==> Running tests..."
PYTHONPATH=".:legacy" python -m pytest tests/test_bot_extended.py::TestVisualizationService -q || {
  echo "ERROR: Tests failed. Fix before deploying."; exit 1
}

# ── Deploy to Cloud Run ──────────────────────────────────────────────
echo "==> Deploying ${SERVICE} to ${REGION}..."
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars "USE_FIRESTORE=true,LOG_LEVEL=INFO" \
  --set-secrets "\
TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,\
GOOGLE_API_KEY=google-api-key:latest,\
SCHEDULER_SECRET=scheduler-secret:latest,\
APPLE_PAY_USER_KEY=apple-pay-user-key:latest,\
APPLE_PAY_CHAT_ID=apple-pay-chat-id:latest"

SERVICE_URL=$(gcloud run services describe "$SERVICE" \
  --region "$REGION" --format='value(status.url)')
echo "==> Service URL: ${SERVICE_URL}"

# ── Set Telegram webhook ─────────────────────────────────────────────
if [[ "${1:-}" != "--no-hook" ]]; then
  echo "==> Setting Telegram webhook..."
  # Fetch bot token from Secret Manager
  TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
  RESULT=$(curl -sf "https://api.telegram.org/bot${TOKEN}/setWebhook?url=${SERVICE_URL}/webhook/telegram")
  echo "    Webhook response: ${RESULT}"
fi

echo ""
echo "==> Done! Deployed to ${SERVICE_URL}"
echo "    Health check:  curl ${SERVICE_URL}/health"
