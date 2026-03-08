# Deploy LegaLens API to Google Cloud Run

## One-time setup

1. **Create a GCP project** (or use an existing one) and set it:
   ```bash
   export PROJECT_ID=your-gcp-project-id
   gcloud config set project $PROJECT_ID
   ```

2. **Enable APIs**:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
   ```

3. **Create an Artifact Registry repository** (for Docker images):
   ```bash
   gcloud artifacts repositories create legalens \
     --repository-format=docker \
     --location=us-central1 \
     --description="LegaLens API images"
   ```

4. **Grant Cloud Build permission to deploy to Cloud Run**:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/run.admin"
   gcloud iam service-accounts add-iam-policy-binding \
     ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser" \
     --project=$PROJECT_ID
   ```

## Deploy

**From the `backend` directory** (so the Dockerfile and `app/` are in the build context):

```bash
cd backend
gcloud builds submit --config=cloudbuild.yaml .
```

After the build finishes, Cloud Run will show the service URL (e.g. `https://legalens-api-xxxxx-uc.a.run.app`).

## Environment variables on Cloud Run

In **Cloud Run → your service → Edit & deploy new revision → Variables & secrets**, add every variable from `.env-example` (use your real secrets). In particular:

- **CORS_ORIGINS**: Your frontend origin(s), e.g. `https://your-app.web.app` or `https://your-domain.com`
- **VOICE_TTS_URL**, **VOICE_TURN_URL**, **LEGALENS_QA_BASE_URL**: Your Cloud Run service URL + path, e.g. `https://legalens-api-xxxxx-uc.a.run.app/api/...`

## Optional: deploy on every push

In **Cloud Build → Triggers**, create a trigger:

- **Source**: your repo (GitHub/GitLab/etc.)
- **Root directory**: `backend`
- **Config**: Cloud Build configuration file, path `backend/cloudbuild.yaml`
- **Substitutions**: override `_SERVICE_NAME`, `_REGION`, `_REPOSITORY` if needed

Save and run the trigger, or let it run on push to your chosen branch.
