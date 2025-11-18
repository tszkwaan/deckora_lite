# Step-by-Step Google Cloud Setup Guide

This guide walks you through setting up Google Cloud for deployment, with options for both **Google Cloud Console (Web UI)** and **gcloud CLI**.

## Prerequisites

- A Google account
- (Optional) `gcloud` CLI installed: https://cloud.google.com/sdk/docs/install

---

## Step 1: Create Google Cloud Project

### Option A: Google Cloud Console (Web UI) ✅ Recommended for beginners

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top
3. Click **"New Project"**
4. Enter project name: `presentation-agent` (or your preferred name)
5. Click **"Create"**
6. **Note your Project ID** (shown in the project dropdown after creation)

### Option B: gcloud CLI

```bash
gcloud projects create presentation-agent --name="Presentation Agent"
gcloud config set project presentation-agent
```

**Get your Project ID:**
```bash
gcloud config get-value project
```

---

## Step 2: Enable Required APIs

### Option A: Google Cloud Console (Web UI)

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

### Option B: gcloud CLI

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

## Step 3: Create Service Account for GitHub Actions

### Option A: Google Cloud Console (Web UI)

1. Go to [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click **"Create Service Account"**
3. Fill in:
   - **Service account name**: `github-actions-sa`
   - **Service account ID**: `github-actions-sa` (auto-filled)
   - **Description**: "Service account for GitHub Actions CI/CD"
4. Click **"Create and Continue"**
5. **Skip** role assignment for now (we'll add roles next)
6. Click **"Done"**

### Option B: gcloud CLI

```bash
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions Service Account" \
  --project=$PROJECT_ID
```

---

## Step 4: Grant Permissions to Service Account

**📘 See [SERVICE_ACCOUNT_PERMISSIONS.md](SERVICE_ACCOUNT_PERMISSIONS.md) for detailed explanation of each role**

### Option A: Google Cloud Console (Web UI)

1. Go to [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click on `github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com`
3. Go to **"Permissions"** tab (you should see "Manage service account permissions")
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

**Note:** You can add all 4 roles in one go by clicking "Add another role" after each selection.

### Option B: gcloud CLI

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

## Step 5: Create and Download Service Account Key

### Option A: Google Cloud Console (Web UI)

1. Go to [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click on `github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com`
3. Go to **"Keys"** tab
4. Click **"Add Key"** → **"Create new key"**
5. Select **JSON** format
6. Click **"Create"**
7. **Save the downloaded file** as `key.json` (you'll need this for GitHub secrets)

⚠️ **Important**: Keep this file secure! Don't commit it to git.

### Option B: gcloud CLI

```bash
gcloud iam service-accounts keys create key.json \
  --iam-account=${SA_EMAIL} \
  --project=$PROJECT_ID
```

---

## Step 6: Upload Credentials to Secret Manager

This stores your Google Slides/Vision API credentials securely.

### Option A: Google Cloud Console (Web UI)

1. Go to [Secret Manager](https://console.cloud.google.com/security/secret-manager)
2. Click **"Create Secret"**
3. Fill in:
   - **Name**: `google-credentials`
   - **Secret value**: Upload or paste contents of `presentation_agent/agents/credentials/credentials.json`
4. Click **"Create Secret"**

### Option B: gcloud CLI

```bash
gcloud secrets create google-credentials \
  --data-file=presentation_agent/agents/credentials/credentials.json \
  --project=$PROJECT_ID
```

---

## Step 6b: Grant Secret Access to Cloud Run Service Account

**⚠️ IMPORTANT:** Cloud Run uses a **different service account** to RUN the container than the one used for deployment.

### Understanding Service Accounts

- **GitHub Actions Service Account** (`deckora-lite@deckora-lite.iam.gserviceaccount.com`):
  - Used to **deploy** the Cloud Run service
  - Needs: Cloud Run Admin, Storage Admin, Artifact Registry Admin, Service Account User

- **Cloud Run Runtime Service Account** (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`):
  - Used to **run** the deployed container
  - Needs: Secret Manager Secret Accessor (to read secrets)
  - This is the **default compute service account** (automatically created)

**The runtime service account needs permission to access secrets!**

### Option A: Google Cloud Console (Web UI)

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

### Option B: gcloud CLI

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

## Step 7: Add Secrets to GitHub

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

## Verification

After completing all steps, verify your setup:

```bash
# Check project is set
gcloud config get-value project

# Check service account exists
gcloud iam service-accounts list --filter="email:github-actions-sa"

# Check APIs are enabled
gcloud services list --enabled --filter="name:cloudbuild OR name:run OR name:containerregistry"

# Verify service account permissions
export SA_EMAIL="github-actions-sa@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:${SA_EMAIL}" \
  --format="table(bindings.role)"
```

### Verify Service Account in GitHub Secrets

To ensure the correct service account is configured in GitHub Actions:

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**
2. Click on `GCP_SA_KEY` secret
3. Copy the JSON content and check the `client_email` field
4. Verify this matches the service account you granted permissions to in Google Cloud Console

**Example:**
```json
{
  "type": "service_account",
  "project_id": "deckora-lite",
  "private_key_id": "...",
  "private_key": "...",
  "client_email": "github-actions-sa@deckora-lite.iam.gserviceaccount.com",  ← Check this!
  ...
}
```

If the `client_email` doesn't match the service account you configured, you need to either:
- Update the `GCP_SA_KEY` secret with the correct service account key, OR
- Grant permissions to the service account shown in `client_email`

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
  --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create key.json \
  --iam-account=${SA_EMAIL}

# Upload credentials to Secret Manager
gcloud secrets create google-credentials \
  --data-file=presentation_agent/agents/credentials/credentials.json

echo "✅ Setup complete! Now add secrets to GitHub:"
echo "   GCP_PROJECT_ID: $PROJECT_ID"
echo "   GCP_SA_KEY: Contents of key.json"
echo "   GOOGLE_API_KEY: Your API key"
```

---

## Troubleshooting

### "Permission denied" errors
- Make sure you're using the correct project ID
- Verify service account has the required roles
- Check that APIs are enabled

### "API not enabled" errors
- Go to Cloud Console → APIs & Services → Enable the missing API

### Can't find service account
- Make sure you're in the correct project
- Check the service account email format: `github-actions-sa@PROJECT_ID.iam.gserviceaccount.com`

