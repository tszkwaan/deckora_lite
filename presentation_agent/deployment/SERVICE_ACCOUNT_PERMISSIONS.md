# Service Account Permissions Guide

## Required Roles for `github-actions-sa`

Your service account needs these **4 required roles** for CI/CD deployment:

### 1. **Cloud Run Admin** (`roles/run.admin`)
**Why needed:** Deploy and manage Cloud Run services
- Deploy new revisions
- Update service configuration
- Manage traffic splitting

### 2. **Storage Admin** (`roles/storage.admin`)
**Why needed:** Legacy GCR support and Cloud Storage access
- Access to legacy Container Registry
- Manage Cloud Storage buckets
- Read/write to Cloud Storage objects

### 3. **Artifact Registry Admin** (`roles/artifactregistry.admin`) ⭐ **Recommended**
**Why needed:** Push Docker images AND create repositories if they don't exist
- Upload Docker images to `gcr.io` (now uses Artifact Registry backend)
- **Create repositories on push** (required if repository doesn't exist yet)
- Push/pull container images
- Manage artifacts in Artifact Registry
- **This role includes create permissions needed for first-time pushes!**

**Alternative:** If you prefer minimal permissions, use `Artifact Registry Writer` + manually create the repository first (see troubleshooting section)

### 4. **Service Account User** (`roles/iam.serviceAccountUser`)
**Why needed:** Use service accounts for Cloud Run deployment
- Impersonate service accounts
- Required for Cloud Run to use service accounts

---

## Optional Roles

### 5. **Service Usage Admin** (`roles/serviceusage.serviceUsageAdmin`) - Optional but Recommended
**Why needed:** Allows the workflow to automatically enable required APIs
- Enable/disable Google Cloud APIs
- **Note:** If you don't grant this role, you must manually enable APIs before first deployment (see DEPLOYMENT_SETUP.md Step 2)

### 6. **Cloud Build Editor** (`roles/cloudbuild.builds.editor`) - Optional
**Why needed:** If you want to use Cloud Build as an alternative
- Create and manage Cloud Build jobs
- View build logs
- **Note:** Not strictly required if using GitHub Actions only

---

## How to Grant Permissions

### Option A: Google Cloud Console (What you're looking at)

1. **You're on the "Permissions" tab** ✅ (correct page!)

2. Click **"Grant Access"** button (top right)

3. In the "New principals" field, enter:
   ```
   github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```
   (Replace `YOUR_PROJECT_ID` with your actual project ID)

4. Click the "Select a role" dropdown and add these roles **one by one**:

   **First role:**
   - Search for: `Cloud Run Admin`
   - Select: `Cloud Run Admin` (roles/run.admin)
   - Click "Add another role"

   **Second role:**
   - Search for: `Storage Admin`
   - Select: `Storage Admin` (roles/storage.admin)
   - Click "Add another role"

   **Third role:**
   - Search for: `Artifact Registry Admin`
   - Select: `Artifact Registry Admin` (roles/artifactregistry.admin) ⭐ **Recommended**
   - Click "Add another role"
   
   **Alternative:** If you prefer minimal permissions, use `Artifact Registry Writer` but you'll need to create the repository manually first

   **Fourth role:**
   - Search for: `Service Account User`
   - Select: `Service Account User` (roles/iam.serviceAccountUser)

5. Click **"Save"**

### Option B: gcloud CLI

```bash
export PROJECT_ID="your-project-id"
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

## Verify Permissions

After granting permissions, verify they're set correctly:

1. On the same "Permissions" tab, you should see:
   - `Cloud Run Admin`
   - `Storage Admin`
   - `Artifact Registry Admin` ⭐ **This is critical for Docker pushes and repo creation!**
   - `Service Account User`

2. Or use CLI:
   ```bash
   gcloud projects get-iam-policy $PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:github-actions-sa@*"
   ```

---

## What Each Role Does (Detailed)

### `roles/run.admin`
- ✅ Deploy services to Cloud Run
- ✅ Update service configuration
- ✅ Manage revisions
- ✅ Set environment variables
- ✅ Configure traffic splitting

### `roles/storage.admin`
- ✅ Legacy GCR support
- ✅ Manage Cloud Storage buckets
- ✅ Read/write object metadata

### `roles/artifactregistry.admin` ⭐ **Recommended - Includes create permissions!**
- ✅ Push Docker images to Container Registry/Artifact Registry
- ✅ **Create repositories on push** (solves "repo does not exist" error)
- ✅ Pull images from registry
- ✅ Upload artifacts to Artifact Registry
- ✅ Required for `gcr.io` (now uses Artifact Registry backend)
- ✅ Full management of Artifact Registry repositories

### `roles/artifactregistry.writer` (Alternative - requires manual repo creation)
- ✅ Push Docker images to Container Registry/Artifact Registry
- ✅ Pull images from registry
- ✅ Upload artifacts to Artifact Registry
- ❌ **Cannot create repositories** - must create manually first

### `roles/iam.serviceAccountUser`
- ✅ Use service accounts in Cloud Run
- ✅ Impersonate service accounts
- ✅ Required for Cloud Run to access other services

---

## Common Issues

### ❌ "Permission denied" when deploying
- **Fix:** Make sure all 3 roles are granted
- **Check:** Verify service account email is correct

### ❌ "Cannot push to Container Registry" or "Permission artifactregistry.repositories.uploadArtifacts denied"
- **Fix:** Grant `Artifact Registry Admin` role (`roles/artifactregistry.admin`)
- **Why:** GCR now uses Artifact Registry backend, so this role is required
- **Note:** `Storage Admin` alone is not sufficient for Docker image pushes

### ❌ "gcr.io repo does not exist. Creating on push requires the artifactregistry.repositories.createOnPush permission"
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

### ❌ "Service account user permission denied"
- **Fix:** Grant `Service Account User` role
- **Note:** This is often forgotten but required!

---

## Minimal Permissions (Advanced)

If you want to use minimal permissions instead of these broad roles, you can grant specific permissions:

- `run.services.create`
- `run.services.update`
- `run.services.get`
- `storage.objects.create`
- `storage.objects.get`
- `storage.buckets.get`
- `iam.serviceAccounts.actAs`

However, using the predefined roles above is **recommended** and **simpler**.

