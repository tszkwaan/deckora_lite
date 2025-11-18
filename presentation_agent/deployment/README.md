# Deployment Configuration

This folder contains all deployment-related files for the Presentation Agent.

## Files

- **`Dockerfile`** - Docker container configuration for Cloud Run
- **`server.py`** - Flask HTTP server for Cloud Run API endpoints
- **`cloudbuild.yaml`** - Google Cloud Build configuration (alternative to GitHub Actions)
- **`.dockerignore`** - Files to exclude from Docker build
- **`DEPLOYMENT.md`** - Main deployment guide
- **`DEPLOYMENT_SETUP.md`** - Step-by-step Google Cloud setup instructions
- **`SERVICE_ACCOUNT_PERMISSIONS.md`** - Service account permissions guide

## GitHub Actions

The GitHub Actions workflow (`.github/workflows/deploy.yml`) references files in this folder:
- Uses `-f presentation_agent/deployment/Dockerfile` to build the image
- The Dockerfile copies the entire project and runs `presentation_agent/deployment/server.py`

## Quick Start

1. See `DEPLOYMENT_SETUP.md` for Google Cloud setup
2. Add secrets to GitHub repository
3. Push to `main` branch - deployment happens automatically!

## API Endpoints

After deployment, the service exposes:
- `GET /health` - Health check
- `POST /generate` - Generate presentation

See the main `README.md` for API documentation.

