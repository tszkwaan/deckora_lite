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
from flask_cors import CORS
from google.adk.sessions import InMemorySessionService

# Import main pipeline components
try:
    from config import PresentationConfig
    from presentation_agent.core.pipeline_orchestrator import PipelineOrchestrator
    from presentation_agent.core.app_initializer import AppInitializer
    
    # Create wrapper function to match old API signature
    async def run_presentation_pipeline(
        config: PresentationConfig,
        output_dir: str = "/tmp/output",
        include_critics: bool = True,
        save_intermediate: bool = True,
        open_browser: bool = False
    ):
        """
        Wrapper function for backward compatibility with server.py.
        Uses the new PipelineOrchestrator under the hood.
        """
        # Initialize application
        initializer = AppInitializer(output_dir=output_dir)
        if not initializer.initialize():
            raise RuntimeError("Failed to initialize application")
        
        # Create and run pipeline orchestrator
        orchestrator = PipelineOrchestrator(
            config=config,
            output_dir=output_dir,
            include_critics=include_critics,
            save_intermediate=save_intermediate,
            open_browser=open_browser,
        )
        
        return await orchestrator.run()
    
except ImportError as e:
    print(f"ERROR: Import error - {e}")
    print(f"Python path: {sys.path}")
    import traceback
    traceback.print_exc()
    run_presentation_pipeline = None
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

# Configure CORS to allow requests from frontend
# Allow all origins for development (restrict in production)
CORS(app, origins="*", methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    if run_presentation_pipeline is None:
        return jsonify({"status": "unhealthy", "error": "Pipeline not loaded"}), 503
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
    if run_presentation_pipeline is None:
        return jsonify({
            "status": "error",
            "error": "Pipeline not initialized"
        }), 500
    
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400
        
        # Validate required fields
        if not data.get("duration"):
            return jsonify({
                "error": "Missing required field: duration is required"
            }), 400
        
        # Create config
        # scenario is optional - if not provided, LLM will infer from report content
        config = PresentationConfig(
            scenario=data.get("scenario") or "",  # Empty string if not provided, will be set to "N/A" in pipeline
            duration=data.get("duration"),
            target_audience=data.get("target_audience"),
            custom_instruction=data.get("custom_instruction", ""),
            report_url=data.get("report_url"),
            report_content=data.get("report_content"),
            style_images=data.get("style_images", [])
        )
        
        # Run the agent pipeline
        async def run_agent():
            logger = logging.getLogger(__name__)
            logger.info("🚀 Starting presentation pipeline execution...")
            
            # Use /tmp/output for Cloud Run (ephemeral writable storage)
            output_dir = "/tmp/output"
            
            outputs = await run_presentation_pipeline(
                config=config,
                output_dir=output_dir,
                include_critics=True,
                save_intermediate=True,
                open_browser=False  # Disable browser opening in Cloud Run
            )
            
            logger.info(f"✅ Pipeline execution completed. Outputs: {list(outputs.keys())}")
            return outputs
        
        # Run async function in a separate thread to avoid event loop conflicts
        # This ensures the async function runs in its own isolated event loop
        import concurrent.futures
        import threading
        
        def run_in_thread():
            """Run the async function in a new event loop in this thread"""
            # Create a new event loop for this thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(run_agent())
            finally:
                new_loop.close()
        
        # Execute in a thread pool to isolate the event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_in_thread)
            outputs = future.result()
        
        # Get logger for response handling
        logger = logging.getLogger(__name__)
        
        # Extract Google Slides URL for easy access in response
        google_slides_url = None
        if outputs.get("slideshow_export_result"):
            slides_result = outputs["slideshow_export_result"]
            if isinstance(slides_result, dict):
                google_slides_url = slides_result.get("shareable_url")
                if not google_slides_url and slides_result.get("presentation_id"):
                    google_slides_url = f"https://docs.google.com/presentation/d/{slides_result.get('presentation_id')}/edit"
        elif outputs.get("slides_export_result"):
             # Fallback if saved under different key
             slides_result = outputs["slides_export_result"]
             if isinstance(slides_result, dict):
                google_slides_url = slides_result.get("shareable_url")
        
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
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

