"""
HTTP server for Cloud Run deployment.
Provides a REST API endpoint to run the presentation generation pipeline.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Enable nested event loops for Flask/gunicorn compatibility
import nest_asyncio
nest_asyncio.apply()

from flask import Flask, request, jsonify
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

# Import with error handling for missing dependencies
try:
    from presentation_agent.agent import root_agent
    from config import PresentationConfig
except ImportError as e:
    print(f"ERROR: Import error - {e}")
    print(f"Python path: {sys.path}")
    print(f"Project root: {project_root}")
    print(f"Project root exists: {project_root.exists()}")
    if project_root.exists():
        print(f"Files in project root: {[f.name for f in project_root.iterdir()]}")
    import traceback
    traceback.print_exc()
    root_agent = None
    PresentationConfig = None


def setup_credentials_from_secret_manager():
    """
    Load credentials.json and token.json from Secret Manager and write them to the expected file paths.
    This runs once at server startup, only if the files don't already exist.
    """
    logger = logging.getLogger(__name__)
    
    # Define expected file paths
    credentials_dir = project_root / "presentation_agent" / "agents" / "credentials"
    credentials_file = credentials_dir / "credentials.json"
    token_file = credentials_dir / "token.json"
    
    # Create directory if it doesn't exist
    credentials_dir.mkdir(parents=True, exist_ok=True)
    
    # Only run in Cloud Run (when PORT env var is set) or if files don't exist locally
    if not os.environ.get('PORT') and credentials_file.exists() and token_file.exists():
        logger.info("✅ Credentials files already exist locally, skipping Secret Manager setup")
        return
    
    logger.info("🔍 Setting up credentials from Secret Manager...")
    
    try:
        from google.cloud import secretmanager
        
        # Get project NUMBER (required for Secret Manager API)
        project_number = os.environ.get('GCP_PROJECT_NUMBER')
        if not project_number:
            try:
                import requests
                logger.info("🔍 Getting project NUMBER from metadata server...")
                project_number = requests.get(
                    'http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id',
                    headers={'Metadata-Flavor': 'Google'},
                    timeout=2
                ).text
                logger.info(f"✅ Got project NUMBER: {project_number}")
            except Exception as e:
                logger.warning(f"⚠️  Could not get project number from metadata: {e}")
                logger.info("⚠️  Skipping Secret Manager setup - not running in Cloud Run or metadata unavailable")
                return
        
        # Use default credentials (Cloud Run provides these automatically via metadata server)
        # Don't use GOOGLE_APPLICATION_CREDENTIALS env var as it might point to OAuth credentials, not service account
        try:
            from google.auth import default as get_default_credentials
            credentials, _ = get_default_credentials()
            client = secretmanager.SecretManagerServiceClient(credentials=credentials)
            logger.info("✅ Using default Cloud Run credentials for Secret Manager access")
        except Exception as e:
            logger.warning(f"⚠️  Could not get default credentials, trying without explicit credentials: {e}")
            # Fallback: try without explicit credentials (should work in Cloud Run)
            client = secretmanager.SecretManagerServiceClient()
        
        # Load credentials.json from Secret Manager
        if not credentials_file.exists():
            try:
                logger.info("🔍 Loading credentials.json from Secret Manager...")
                secret_name = f"projects/{project_number}/secrets/google-credentials/versions/latest"
                response = client.access_secret_version(request={"name": secret_name})
                credentials_json = response.payload.data.decode('UTF-8')
                
                # Validate JSON
                json.loads(credentials_json)
                
                # Write to file
                with open(credentials_file, 'w') as f:
                    f.write(credentials_json)
                logger.info(f"✅ Successfully wrote credentials.json to {credentials_file}")
            except Exception as e:
                logger.error(f"❌ Failed to load credentials.json from Secret Manager: {e}")
                # Don't raise - allow the app to start, but credentials will fail later
        else:
            logger.info(f"✅ credentials.json already exists at {credentials_file}")
        
        # Load token.json from Secret Manager
        if not token_file.exists():
            try:
                logger.info("🔍 Loading token.json from Secret Manager...")
                secret_name = f"projects/{project_number}/secrets/google-token/versions/latest"
                response = client.access_secret_version(request={"name": secret_name})
                token_json = response.payload.data.decode('UTF-8')
                
                # Validate JSON
                json.loads(token_json)
                
                # Write to file
                with open(token_file, 'w') as f:
                    f.write(token_json)
                logger.info(f"✅ Successfully wrote token.json to {token_file}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to load token.json from Secret Manager: {e}")
                logger.info("   This is OK if token secret doesn't exist yet - OAuth flow will be needed")
        else:
            logger.info(f"✅ token.json already exists at {token_file}")
        
        logger.info("✅ Credentials setup complete")
        
    except ImportError:
        logger.warning("⚠️  Secret Manager library not available - skipping credential setup")
    except Exception as e:
        logger.error(f"❌ Error setting up credentials from Secret Manager: {e}")
        import traceback
        logger.error(traceback.format_exc())


# Setup credentials from Secret Manager before creating Flask app
setup_credentials_from_secret_manager()

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    if root_agent is None:
        return jsonify({"status": "unhealthy", "error": "Agent not loaded"}), 503
    return jsonify({"status": "healthy"}), 200


@app.route('/generate', methods=['POST'])
def generate_presentation():
    """
    Generate a presentation from a research report.
    
    Expected JSON payload:
    {
        "report_url": "https://arxiv.org/pdf/...",
        "report_content": "...",  # Optional if report_url provided
        "scenario": "academic_teaching",
        "duration": "20 minutes",
        "target_audience": "students",  # Optional
        "custom_instruction": "keep slides clean"
    }
    
    Returns:
        JSON response with presentation results
    """
    if root_agent is None:
        return jsonify({
            "status": "error",
            "error": "Agent not initialized"
        }), 500
    
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400
        
        # Validate required fields
        if not data.get("scenario") or not data.get("duration"):
            return jsonify({
                "error": "Missing required fields: scenario and duration are required"
            }), 400
        
        # Create config
        config = PresentationConfig(
            scenario=data.get("scenario"),
            duration=data.get("duration"),
            target_audience=data.get("target_audience"),
            custom_instruction=data.get("custom_instruction", ""),
            report_url=data.get("report_url"),
            report_content=data.get("report_content"),
            style_images=data.get("style_images", [])
        )
        
        # Build initial message
        target_audience_section = (
            f"[TARGET_AUDIENCE]\n{config.target_audience}\n"
            if config.target_audience
            else "[TARGET_AUDIENCE]\nN/A\n"
        )
        
        initial_message = f"""
[SCENARIO]
{config.scenario}

[DURATION]
{config.duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{config.custom_instruction}

[REPORT_URL]
{config.report_url or 'N/A'}

[REPORT_CONTENT]
{config.report_content or ''}
[END_REPORT_CONTENT]

Your task:
- Use ONLY the above information.
- Generate a complete presentation following the pipeline.
- Do NOT ask any questions.
- Do NOT invent information not in the report_content.
"""
        
        # Run the agent pipeline
        async def run_agent():
            session_service = InMemorySessionService()
            session = await session_service.create_session(
                app_name="presentation_agent",
                user_id="user"
            )
            
            # Set up session state
            session.state.update(config.to_dict())
            
            # Create runner and execute
            runner = InMemoryRunner(agent=root_agent)
            events = await runner.run_debug(initial_message, session_id=session.id)
            
            # Debug: Log all keys in session.state
            logger = logging.getLogger(__name__)
            logger.info(f"🔍 Session state keys after pipeline: {list(session.state.keys())}")
            logger.info(f"🔍 Session state full content: {json.dumps(dict(session.state), indent=2, default=str)}")
            
            # Extract outputs from session state
            outputs = {}
            if session.state.get("report_knowledge"):
                outputs["report_knowledge"] = session.state["report_knowledge"]
                logger.info("✅ Found report_knowledge in session.state")
            if session.state.get("presentation_outline"):
                outputs["presentation_outline"] = session.state["presentation_outline"]
                logger.info("✅ Found presentation_outline in session.state")
            if session.state.get("slide_and_script"):
                outputs["slide_and_script"] = session.state["slide_and_script"]
                logger.info("✅ Found slide_and_script in session.state")
            if session.state.get("slides_export_result"):
                outputs["slides_export_result"] = session.state["slides_export_result"]
                logger.info("✅ Found slides_export_result in session.state")
            if session.state.get("layout_review"):
                outputs["layout_review"] = session.state["layout_review"]
                logger.info("✅ Found layout_review in session.state")
            
            logger.info(f"🔍 Extracted outputs: {list(outputs.keys())}")
            
            return outputs
        
        # Run async function
        outputs = asyncio.run(run_agent())
        
        # Return results
        return jsonify({
            "status": "success",
            "outputs": outputs
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

