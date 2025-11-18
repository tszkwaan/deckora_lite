# Deployment Guide - Vertex AI Agent Engine

This guide explains how to deploy the Presentation Agent to Vertex AI Agent Engine using GitHub Actions CI/CD, following the [Kaggle tutorial](https://www.kaggle.com/code/kaggle5daysofai/day-5b-agent-deployment).

## Prerequisites

**📘 For detailed step-by-step setup instructions, see [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md)**

Quick summary:

1. **Google Cloud Project**
   - Create a project in [Google Cloud Console](https://console.cloud.google.com/)
   - Note your Project ID

2. **Enable Required APIs**
   - Vertex AI API (`aiplatform.googleapis.com`)
   - Artifact Registry API (`artifactregistry.googleapis.com`)
   - Secret Manager API (`secretmanager.googleapis.com`)
   - Storage API (`storage-api.googleapis.com`)

3. **Service Account**
   - Create service account for GitHub Actions
   - Grant roles: Vertex AI User, Storage Admin, Service Account User
   - Download JSON key file

4. **Google Cloud Credentials**
   - Upload `credentials.json` to Secret Manager (for Google Slides/Vision APIs)

## GitHub Repository Setup

1. **Add Secrets**
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Click **"New repository secret"** and add:
     - `GCP_PROJECT_ID`: Your Google Cloud project ID
     - `GCP_SA_KEY`: Contents of the service account key JSON file
     - `GOOGLE_API_KEY`: Your Google API key for Gemini

2. **Push to Main Branch**
   - The workflow automatically triggers on push to `main` branch
   - Or manually trigger from Actions tab → "Deploy to Vertex AI Agent Engine" → "Run workflow"

## Deployment Process

The GitHub Actions workflow will:

1. **Enable Required APIs**
   - Enables Vertex AI, Artifact Registry, Secret Manager, and Storage APIs

2. **Install Dependencies**
   - Installs Python dependencies including `google-cloud-aiplatform[agent_engines,adk]`

3. **Deploy to Vertex AI Agent Engine**
   - Uses ADK's `AgentEngine` to deploy the agent
   - Packages the agent with all required dependencies
   - Creates a Vertex AI Agent Engine resource

4. **Verify Deployment**
   - Shows agent resource name and ID
   - Provides link to view agent in Google Cloud Console

## Accessing Your Deployed Agent

After deployment, your agent will be available in Vertex AI Agent Engine:

1. **View in Console:**
   - Go to [Vertex AI → Agents](https://console.cloud.google.com/vertex-ai/agents)
   - Select your project
   - Find your agent: `presentation-agent`

2. **Use the Agent:**
   - The agent can be invoked via Vertex AI Agent Engine APIs
   - Or integrated into other applications using the Agent Engine SDK

## Local Deployment (Alternative)

You can also deploy locally using the deployment script:

```bash
# Install dependencies
pip install -r requirements.txt
pip install google-cloud-aiplatform[agent_engines,adk]

# Set environment variables
export GOOGLE_API_KEY="your-api-key"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"

# Deploy
python presentation_agent/deployment/deploy_to_agent_engine.py \
  --project-id YOUR_PROJECT_ID \
  --location us-central1 \
  --agent-name presentation-agent
```

## Differences from Cloud Run Deployment

- **No Docker**: Agent Engine handles containerization automatically
- **No Flask Server**: Agent is deployed directly as an ADK agent
- **Managed Infrastructure**: Vertex AI handles scaling and infrastructure
- **Native ADK Integration**: Better integration with ADK features and tooling

## Troubleshooting

### "Permission denied" errors
- Ensure service account has `roles/aiplatform.user` role
- Verify APIs are enabled

### "Agent deployment failed"
- Check that all dependencies are listed in `requirements.txt`
- Verify `root_agent` is properly exported from `presentation_agent/agent.py`
- Check logs in Cloud Console for detailed error messages

### Import errors
- Ensure `google-cloud-aiplatform[agent_engines,adk]` is installed
- Verify all agent dependencies are in `requirements.txt`

