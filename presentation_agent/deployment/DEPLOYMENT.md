# Deployment Guide

This guide covers deploying the Presentation Agent to **Google Cloud Run**.

## Table of Contents

1. [Prerequisites & Setup](#prerequisites--setup)
2. [Service Account Permissions](#service-account-permissions)
3. [Cloud Run Deployment](#cloud-run-deployment)
4. [Troubleshooting](#troubleshooting)

---

## Prerequisites & Setup

### Step 1: Create Google Cloud Project

#### Option A: Google Cloud Console (Web UI) ✅ Recommended for beginners

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top
3. Click **"New Project"**
4. Enter project name: `presentation-agent` (or your preferred name)
5. Click **"Create"**
6. **Note your Project ID** (shown in the project dropdown after creation)

#### Option B: gcloud CLI

```bash
gcloud projects create presentation-agent --name="Presentation Agent"
gcloud config set project presentation-agent
```

**Get your Project ID:**
```bash
gcloud config get-value project
```

---

### Step 2: Enable Required APIs

#### Option A: Google Cloud Console (Web UI)

1. Go to [APIs & Services → Library](https://console.cloud.google.com/apis/library)
2. Search for and enable each of these APIs:
   - **Cloud Build API** (`cloudbuild.googleapis.com`)
   - **Cloud Run API** (`run.googleapis.com`)
   - **Artifact Registry API** (`artifactregistry.googleapis.com`) ⭐ **Required for Docker image pushes**
   - **Container Registry API** (`containerregistry.googleapis.com`) (legacy, but still needed)
   - **Secret Manager API** (`secretmanager.googleapis.com`) (for storing credentials)

For each API:
- Click on the API name
- Click **"Enable"** button

#### Option B: gcloud CLI

```bash
# Set your project ID first
export PROJECT_ID="your-project-id"

# Enable all required APIs at once
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  containerregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project=$PROJECT_ID
```

---

### Step 3: Create Service Account for GitHub Actions

#### Option A: Google Cloud Console (Web UI)

1. Go to [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click **"Create Service Account"**
3. Fill in:
   - **Service account name**: `github-actions-sa`
   - **Service account ID**: `github-actions-sa` (auto-filled)
   - **Description**: "Service account for GitHub Actions CI/CD"
4. Click **"Create and Continue"**
5. **Skip** role assignment for now (we'll add roles next)
6. Click **"Done"**

#### Option B: gcloud CLI

```bash
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions Service Account" \
  --project=$PROJECT_ID
```

---

### Step 4: Grant Permissions to Service Account

See [Service Account Permissions](#service-account-permissions) section below for detailed role explanations.

#### Option A: Google Cloud Console (Web UI)

1. Go to [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click on `github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com`
3. Go to **"Permissions"** tab
4. Click **"Grant Access"** button (top right)
5. In the dialog:
   - **New principals**: Enter `github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com`
   - **Select a role**: Add these **4 required roles**:
     - **Cloud Run Admin** (`roles/run.admin`) - for deploying to Cloud Run
     - **Storage Admin** (`roles/storage.admin`) - for legacy GCR support
     - **Artifact Registry Admin** (`roles/artifactregistry.admin`) - ⭐ **REQUIRED for pushing Docker images and creating repositories**
     - **Service Account User** (`roles/iam.serviceAccountUser`) - for using service accounts
   - Click **"Add another role"** after each one
6. Click **"Save"**

#### Option B: gcloud CLI

```bash
export SA_EMAIL="github-actions-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant Cloud Run Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

# Grant Storage Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"

# Grant Artifact Registry Admin (REQUIRED for Docker image pushes + repo creation)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.admin"

# Grant Service Account User
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
```

---

### Step 5: Create and Download Service Account Key

#### Option A: Google Cloud Console (Web UI)

1. Go to [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click on `github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com`
3. Go to **"Keys"** tab
4. Click **"Add Key"** → **"Create new key"**
5. Select **JSON** format
6. Click **"Create"**
7. **Save the downloaded file** as `key.json` (you'll need this for GitHub secrets)

⚠️ **Important**: Keep this file secure! Don't commit it to git.

#### Option B: gcloud CLI

```bash
gcloud iam service-accounts keys create key.json \
  --iam-account=${SA_EMAIL} \
  --project=$PROJECT_ID
```

---

### Step 6: Upload Credentials to Secret Manager

This stores your Google Slides/Vision API credentials securely.

#### Option A: Google Cloud Console (Web UI)

1. Go to [Secret Manager](https://console.cloud.google.com/security/secret-manager)
2. Click **"Create Secret"**
3. Fill in:
   - **Name**: `google-credentials`
   - **Secret value**: Upload or paste contents of `presentation_agent/agents/credentials/credentials.json`
4. Click **"Create Secret"**

#### Option B: gcloud CLI

```bash
gcloud secrets create google-credentials \
  --data-file=presentation_agent/agents/credentials/credentials.json \
  --project=$PROJECT_ID
```

---

### Step 6b: Grant Secret Access to Cloud Run Service Account

**⚠️ IMPORTANT:** Cloud Run uses a **different service account** to RUN the container than the one used for deployment.

#### Understanding Service Accounts

- **GitHub Actions Service Account** (`github-actions-sa@PROJECT_ID.iam.gserviceaccount.com`):
  - Used to **deploy** the Cloud Run service
  - Needs: Cloud Run Admin, Storage Admin, Artifact Registry Admin, Service Account User

- **Cloud Run Runtime Service Account** (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`):
  - Used to **run** the deployed container
  - Needs: Secret Manager Secret Accessor (to read secrets)
  - This is the **default compute service account** (automatically created)

**The runtime service account needs permission to access secrets!**

#### Option A: Google Cloud Console (Web UI)

1. Go to [Secret Manager](https://console.cloud.google.com/security/secret-manager)
2. Click on the `google-credentials` secret
3. Click **"Permissions"** tab
4. Click **"Grant Access"**
5. In the dialog:
   - **New principals**: Enter `PROJECT_NUMBER-compute@developer.gserviceaccount.com`
     - To find your project number:
       - Go to [Cloud Console Home](https://console.cloud.google.com/home/dashboard)
       - Your project number is shown next to the project name (e.g., `385552249410`)
     - Example: `385552249410-compute@developer.gserviceaccount.com`
   - **Select a role**: `Secret Manager Secret Accessor` (`roles/secretmanager.secretAccessor`)
6. Click **"Save"**

#### Option B: gcloud CLI

```bash
export PROJECT_ID="your-project-id"

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Cloud Run Runtime Service Account: ${COMPUTE_SA}"

# Grant secret access
gcloud secrets add-iam-policy-binding google-credentials \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

**Note:** The GitHub Actions workflow will attempt to grant this automatically, but you can also do it manually.

---

### Step 7: Add Secrets to GitHub

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Add these secrets:

   **Secret 1: `GCP_PROJECT_ID`**
   - Name: `GCP_PROJECT_ID`
   - Value: Your project ID (e.g., `presentation-agent-123456`)

   **Secret 2: `GCP_SA_KEY`**
   - Name: `GCP_SA_KEY`
   - Value: **Entire contents** of the `key.json` file you downloaded
     - Open `key.json` in a text editor
     - Copy **all** the JSON content (including `{` and `}`)
     - Paste into the secret value

   **Secret 3: `GOOGLE_API_KEY`**
   - Name: `GOOGLE_API_KEY`
   - Value: Your Google API key for Gemini

---

## Service Account Permissions

### Required Roles for `github-actions-sa`

Your service account needs these **4 required roles** for CI/CD deployment:

#### 1. **Cloud Run Admin** (`roles/run.admin`)
**Why needed:** Deploy and manage Cloud Run services
- Deploy new revisions
- Update service configuration
- Manage traffic splitting

#### 2. **Storage Admin** (`roles/storage.admin`)
**Why needed:** Legacy GCR support and Cloud Storage access
- Access to legacy Container Registry
- Manage Cloud Storage buckets
- Read/write to Cloud Storage objects

#### 3. **Artifact Registry Admin** (`roles/artifactregistry.admin`) ⭐ **Recommended**
**Why needed:** Push Docker images AND create repositories if they don't exist
- Upload Docker images to `gcr.io` (now uses Artifact Registry backend)
- **Create repositories on push** (required if repository doesn't exist yet)
- Push/pull container images
- Manage artifacts in Artifact Registry
- **This role includes create permissions needed for first-time pushes!**

**Alternative:** If you prefer minimal permissions, use `Artifact Registry Writer` + manually create the repository first

#### 4. **Service Account User** (`roles/iam.serviceAccountUser`)
**Why needed:** Use service accounts for Cloud Run deployment
- Impersonate service accounts
- Required for Cloud Run to use service accounts

### Optional Roles

#### 5. **Service Usage Admin** (`roles/serviceusage.serviceUsageAdmin`) - Optional but Recommended
**Why needed:** Allows the workflow to automatically enable required APIs
- Enable/disable Google Cloud APIs
- **Note:** If you don't grant this role, you must manually enable APIs before first deployment

#### 6. **Cloud Build Editor** (`roles/cloudbuild.builds.editor`) - Optional
**Why needed:** If you want to use Cloud Build as an alternative
- Create and manage Cloud Build jobs
- View build logs
- **Note:** Not strictly required if using GitHub Actions only

---

## Cloud Run Deployment

This guide explains how to deploy the Presentation Agent to Google Cloud Run using GitHub Actions CI/CD.

### GitHub Repository Setup

1. **Add Secrets** (if not already done in Step 7)
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Click **"New repository secret"** and add:
     - `GCP_PROJECT_ID`: Your Google Cloud project ID
     - `GCP_SA_KEY`: Contents of the `key.json` file (from service account creation)
     - `GOOGLE_API_KEY`: Your Google API key for Gemini

2. **Push to Main Branch**
   - The workflow automatically triggers on push to `main` branch
   - Or manually trigger from Actions tab → "Deploy to Google Cloud Run" → "Run workflow"

### Deployment Process

The GitHub Actions workflow will:

1. **Build Docker Image**
   - Creates a Docker image with all dependencies
   - Tags it with commit SHA and `latest`

2. **Push to Google Container Registry**
   - Uploads image to `gcr.io/YOUR_PROJECT_ID/presentation-agent`

3. **Deploy to Cloud Run**
   - Deploys the containerized agent
   - Configures environment variables and secrets
   - Sets resource limits (2GB RAM, 2 CPU, 1 hour timeout)

4. **Test Deployment**
   - Runs health check to verify deployment

### API Endpoints

Once deployed, your agent will be available at:
```
https://presentation-agent-XXXXX-uc.a.run.app
```

#### Health Check
```bash
curl https://YOUR_SERVICE_URL/health
```

#### Generate Presentation
```bash
curl -X POST https://YOUR_SERVICE_URL/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report_url": "https://arxiv.org/pdf/2511.08597",
    "scenario": "academic_teaching",
    "duration": "20 minutes",
    "target_audience": "students",
    "custom_instruction": "keep slides clean"
  }'
```

### Local Testing

Test the Docker image locally before deploying:

```bash
# Build image
docker build -f presentation_agent/deployment/Dockerfile -t presentation-agent:local .

# Run container
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=your-key \
  -e GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json \
  -v /path/to/credentials.json:/app/credentials.json \
  presentation-agent:local

# Test health endpoint
curl http://localhost:8080/health
```

### Environment Variables

The following environment variables are set in Cloud Run:

- `GOOGLE_API_KEY`: Gemini API key (from GitHub secrets)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to credentials.json (from Secret Manager)
- `PORT`: Server port (default: 8080)

### Monitoring and Logs

View logs in Google Cloud Console:
```bash
gcloud run services logs read presentation-agent --region us-central1
```

Or in the Cloud Console:
- Navigate to Cloud Run → presentation-agent → Logs

---

## Troubleshooting

### Build Fails
- Check that all dependencies are in `requirements.txt`
- Verify Dockerfile syntax
- Check GitHub Actions logs for specific errors

### Deployment Fails
- Verify service account has correct permissions
- Check that secrets are correctly set in GitHub
- Ensure APIs are enabled in GCP project

### Runtime Errors
- Check Cloud Run logs for error messages
- Verify `GOOGLE_API_KEY` is set correctly
- Ensure credentials.json is accessible via Secret Manager

### "Permission denied on secret" Error
- **Fix**: Grant `Secret Manager Secret Accessor` role to Cloud Run service account:
  ```bash
  export PROJECT_ID="your-project-id"
  export COMPUTE_SA="${PROJECT_ID}-compute@developer.gserviceaccount.com"
  
  gcloud secrets add-iam-policy-binding google-credentials \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID
  ```
- Or via Console: Secret Manager → `google-credentials` → Permissions → Grant Access → Add `PROJECT_ID-compute@developer.gserviceaccount.com` with `Secret Manager Secret Accessor` role

### "Permission denied" errors
- Make sure you're using the correct project ID
- Verify service account has the required roles
- Check that APIs are enabled

### "API not enabled" errors
- Go to Cloud Console → APIs & Services → Enable the missing API

### "Cannot push to Container Registry" or "Permission artifactregistry.repositories.uploadArtifacts denied"
- **Fix**: Grant `Artifact Registry Admin` role (`roles/artifactregistry.admin`)
- **Why:** GCR now uses Artifact Registry backend, so this role is required
- **Note:** `Storage Admin` alone is not sufficient for Docker image pushes

### "gcr.io repo does not exist. Creating on push requires the artifactregistry.repositories.createOnPush permission"
- **Fix Option 1 (Recommended):** Grant `Artifact Registry Admin` role (`roles/artifactregistry.admin`)
  - This role includes create permissions, so repositories are created automatically on first push
- **Fix Option 2:** Manually create the repository first:
  ```bash
  gcloud artifacts repositories create gcr.io \
    --repository-format=docker \
    --location=us \
    --project=$PROJECT_ID
  ```
  Then `Artifact Registry Writer` role is sufficient

### "Service account user permission denied"
- **Fix:** Grant `Service Account User` role
- **Note:** This is often forgotten but required!

---

## Security Notes

- Never commit `credentials.json` or API keys to git
- Use Secret Manager for sensitive data
- Service account keys are stored as GitHub secrets
- Cloud Run service is publicly accessible (consider adding authentication if needed)

---

## Quick Reference: All Commands (gcloud CLI)

If you prefer to do everything via CLI:

```bash
# Set variables
export PROJECT_ID="your-project-id"
export SA_EMAIL="github-actions-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Create project (if not exists)
gcloud projects create $PROJECT_ID --name="Presentation Agent"
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com \
  secretmanager.googleapis.com

# Create service account
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create key.json \
  --iam-account=${SA_EMAIL}

# Upload credentials to Secret Manager
gcloud secrets create google-credentials \
  --data-file=presentation_agent/agents/credentials/credentials.json

# Grant secret access to Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding google-credentials \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID

echo "✅ Setup complete! Now add secrets to GitHub:"
echo "   GCP_PROJECT_ID: $PROJECT_ID"
echo "   GCP_SA_KEY: Contents of key.json"
echo "   GOOGLE_API_KEY: Your API key"
```
