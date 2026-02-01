# Deploying to Google Cloud Run

## Prerequisites

- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed
- A GCP project with billing enabled (free tier is sufficient)

## 1. Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

## 2. Create Firestore Database

```bash
gcloud firestore databases create --location=us-east1
```

## 3. Store Secrets

```bash
echo -n "YOUR_BOT_TOKEN" | gcloud secrets create telegram-bot-token --data-file=-
echo -n "YOUR_GOOGLE_API_KEY" | gcloud secrets create google-api-key --data-file=-
echo -n "YOUR_SCHEDULER_SECRET" | gcloud secrets create scheduler-secret --data-file=-
echo -n "YOUR_APPLE_PAY_USER_KEY" | gcloud secrets create apple-pay-user-key --data-file=-
```

## 4. Migrate Existing Data (optional)

If you have existing SQLite databases in `user_data/`:

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
python migrate_to_firestore.py
```

## 5. Deploy to Cloud Run

```bash
gcloud run deploy my-budget-bot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars "USE_FIRESTORE=true,APPLE_PAY_USER_KEY=YOUR_USER_ID,LOG_LEVEL=INFO" \
  --set-secrets "\
TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,\
GOOGLE_API_KEY=google-api-key:latest,\
SCHEDULER_SECRET=scheduler-secret:latest,\
APPLE_PAY_USER_KEY=apple-pay-user-key:latest"
```

Note the service URL from the output (e.g. `https://my-budget-bot-XXXX.run.app`).

## 6. Set Telegram Webhook

Replace `<TOKEN>` and `<URL>` with your values:

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL>/webhook/telegram"
```

## 7. Create Cloud Scheduler Jobs

```bash
SERVICE_URL=$(gcloud run services describe my-budget-bot --region us-central1 --format='value(status.url)')

# Daily report at 9 PM
gcloud scheduler jobs create http daily-report \
  --schedule="0 21 * * *" \
  --time-zone="YOUR_TIMEZONE" \
  --uri="${SERVICE_URL}/internal/daily-report" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=YOUR_SCHEDULER_SECRET"

# Monthly report on the 1st at 9 AM
gcloud scheduler jobs create http monthly-report \
  --schedule="0 9 1 * *" \
  --time-zone="YOUR_TIMEZONE" \
  --uri="${SERVICE_URL}/internal/monthly-report" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=YOUR_SCHEDULER_SECRET"
```

## Cost

| Service | Free Tier |
|---------|-----------|
| Cloud Run | 2M requests, 360K vCPU-sec/month |
| Firestore | 1GB storage, 50K reads/day, 20K writes/day |
| Cloud Scheduler | 3 jobs free |
| Cloud Build | 120 min/day |

For a personal budget bot, usage will be well within free tier limits.

**Cold starts**: First message after idle takes ~3-5 seconds. Subsequent
messages are instant while the instance stays warm.
