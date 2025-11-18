#!/bin/bash
# Script to manually create GCR repository
# Run this once to create the repository, then deployments will work

set -e

# Get project ID from environment or prompt
if [ -z "$PROJECT_ID" ]; then
    echo "Enter your Google Cloud Project ID:"
    read PROJECT_ID
fi

echo "Creating GCR repository for project: $PROJECT_ID"

# Create the repository in us region (GCR uses us as default)
gcloud artifacts repositories create gcr.io \
  --repository-format=docker \
  --location=us \
  --project=$PROJECT_ID \
  --description="Docker repository for presentation-agent"

echo "✅ Repository created successfully!"
echo "You can now push Docker images to: gcr.io/$PROJECT_ID/presentation-agent"

