# Deployment Guide - Google Cloud Run

This guide explains how to deploy the Presentation Agent to Google Cloud Run using GitHub Actions CI/CD.

## Prerequisites

**📘 For detailed step-by-step setup instructions, see [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md)**

Quick summary:

1. **Google Cloud Project**
   - Create a project in [Google Cloud Console](https://console.cloud.google.com/)
   - Note your Project ID

2. **Enable Required APIs**
   - Use Cloud Console UI or CLI (see DEPLOYMENT_SETUP.md)

3. **Service Account**
   - Create `github-actions-sa` service account
   - Grant roles: Cloud Run Admin, Storage Admin, Service Account User
   - Download JSON key file

4. **Google Cloud Credentials**
   - Upload `credentials.json` to Secret Manager

## GitHub Repository Setup

1. **Add Secrets**
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Add the following secrets:
     - `GCP_PROJECT_ID`: Your Google Cloud project ID
     - `GCP_SA_KEY`: Contents of the `key.json` file (from service account creation)
     - `GOOGLE_API_KEY`: Your Google API key for Gemini

2. **Push to Main Branch**
   - The workflow automatically triggers on push to `main` branch
   - Or manually trigger from Actions tab → "Deploy to Google Cloud Run" → "Run workflow"

## Deployment Process

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

## API Endpoints

Once deployed, your agent will be available at:
```
https://presentation-agent-XXXXX-uc.a.run.app
```

### Health Check
```bash
curl https://YOUR_SERVICE_URL/health
```

### Generate Presentation
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

## Local Testing

Test the Docker image locally before deploying:

```bash
# Build image
docker build -t presentation-agent:local .

# Run container
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=your-key \
  -e GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json \
  -v /path/to/credentials.json:/app/credentials.json \
  presentation-agent:local

# Test health endpoint
curl http://localhost:8080/health
```

## Environment Variables

The following environment variables are set in Cloud Run:

- `GOOGLE_API_KEY`: Gemini API key (from GitHub secrets)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to credentials.json (from Secret Manager)
- `PORT`: Server port (default: 8080)

## Monitoring and Logs

View logs in Google Cloud Console:
```bash
gcloud run services logs read presentation-agent --region us-central1
```

Or in the Cloud Console:
- Navigate to Cloud Run → presentation-agent → Logs

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

## Cost Considerations

Cloud Run pricing:
- **CPU**: Billed per request (first 2M requests free/month)
- **Memory**: Billed per GB-second
- **Timeout**: Max 1 hour per request

Estimated cost for moderate usage: ~$10-50/month

## Security Notes

- Never commit `credentials.json` or API keys to git
- Use Secret Manager for sensitive data
- Service account keys are stored as GitHub secrets
- Cloud Run service is publicly accessible (consider adding authentication if needed)

