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


def verify_credentials_files():
    """
    Verify that credentials.json and token.json exist at expected paths.
    In Cloud Run, these should be mounted as files via --update-secrets.
    In local development, they should exist in the credentials directory.
    """
    logger = logging.getLogger(__name__)
    
    # Define expected file paths
    credentials_dir = project_root / "presentation_agent" / "agents" / "credentials"
    credentials_file = credentials_dir / "credentials.json"
    token_file = credentials_dir / "token.json"
    
    # Create directory if it doesn't exist (for local development)
    credentials_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if files exist
    credentials_exist = credentials_file.exists()
    token_exist = token_file.exists()
    
    if credentials_exist and token_exist:
        logger.info(f"✅ Credentials files found:")
        logger.info(f"   - credentials.json: {credentials_file}")
        logger.info(f"   - token.json: {token_file}")
        return True
    else:
        missing = []
        if not credentials_exist:
            missing.append("credentials.json")
        if not token_exist:
            missing.append("token.json")
        
        logger.warning(f"⚠️  Missing credential files: {', '.join(missing)}")
        if os.environ.get('PORT'):
            logger.warning("   In Cloud Run, credentials should be included in Docker image from GitHub Secrets")
            logger.warning("   Expected paths:")
            logger.warning(f"   - {credentials_file}")
            logger.warning(f"   - {token_file}")
        else:
            logger.warning("   For local development, place files in:")
            logger.warning(f"   - {credentials_dir}")
        return False


# Verify credentials files exist before creating Flask app
verify_credentials_files()

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
                slides_export_result = session.state["slides_export_result"]
                outputs["slides_export_result"] = slides_export_result
                logger.info("✅ Found slides_export_result in session.state")
                
                # Extract Google Slides URL from slides_export_result
                if isinstance(slides_export_result, dict):
                    shareable_url = slides_export_result.get("shareable_url")
                    presentation_id = slides_export_result.get("presentation_id")
                    status = slides_export_result.get("status", "unknown")
                    
                    if shareable_url:
                        outputs["google_slides_url"] = shareable_url
                        logger.info(f"✅ Google Slides URL: {shareable_url}")
                    elif presentation_id:
                        # Generate URL from ID if shareable_url not available
                        generated_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
                        outputs["google_slides_url"] = generated_url
                        logger.info(f"✅ Google Slides URL (generated from ID): {generated_url}")
                    
                    if status:
                        outputs["export_status"] = status
                        logger.info(f"✅ Export status: {status}")
            if session.state.get("layout_review"):
                outputs["layout_review"] = session.state["layout_review"]
                logger.info("✅ Found layout_review in session.state")
            
            logger.info(f"🔍 Extracted outputs: {list(outputs.keys())}")
            
            return outputs
        
        # Run async function
        outputs = asyncio.run(run_agent())
        
               # Extract Google Slides URL for easy access in response
               google_slides_url = None
               if outputs.get("slides_export_result"):
                   slides_result = outputs["slides_export_result"]
                   if isinstance(slides_result, dict):
                       google_slides_url = slides_result.get("shareable_url")
                       if not google_slides_url and slides_result.get("presentation_id"):
                           google_slides_url = f"https://docs.google.com/presentation/d/{slides_result.get('presentation_id')}/edit"
               
               # Return results
               response = {
                   "status": "success",
                   "outputs": outputs
               }
               
               # Add Google Slides URL at top level for easy access
               if google_slides_url:
                   response["google_slides_url"] = google_slides_url
                   logger.info(f"✅ Returning Google Slides URL in response: {google_slides_url}")
               
               return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

