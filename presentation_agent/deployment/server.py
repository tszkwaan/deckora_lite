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
from presentation_agent.agents.utils.helpers import extract_output_from_events

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
            logger.info(f"🔍 Total events: {len(events)}")
            logger.info(f"🔍 Session state keys after pipeline: {list(session.state.keys())}")
            
            # Detailed event inspection for debugging
            logger.info("🕵️ DETAILED EVENT INSPECTION:")
            slides_export_events = []
            for i, event in enumerate(events):
                agent_name = getattr(event, 'agent_name', None) or (event.agent.name if hasattr(event, 'agent') and hasattr(event.agent, 'name') else 'Unknown')
                event_type = type(event).__name__
                logger.info(f"   Event {i}: Type={event_type}, Agent={agent_name}")
                
                # Track SlidesExportAgent events specifically
                if 'SlidesExport' in agent_name:
                    slides_export_events.append(i)
                    logger.info(f"      ⭐ SLIDES EXPORT EVENT DETECTED at index {i}")
                
                # Check state_delta
                if hasattr(event, 'actions') and event.actions and hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                    delta_keys = list(event.actions.state_delta.keys())
                    logger.info(f"      state_delta keys: {delta_keys}")
                    if 'slides_export_result' in delta_keys:
                        logger.info(f"      ✅✅✅ FOUND slides_export_result in state_delta!")
                        result = event.actions.state_delta['slides_export_result']
                        logger.info(f"         Result type: {type(result).__name__}")
                        if isinstance(result, dict):
                            logger.info(f"         Result keys: {list(result.keys())}")
                            logger.info(f"         Status: {result.get('status', 'N/A')}")
                            logger.info(f"         URL: {result.get('shareable_url', 'N/A')}")
                    
                # Check tool results
                if hasattr(event, 'actions') and event.actions and hasattr(event.actions, 'tool_results') and event.actions.tool_results:
                    logger.info(f"      tool_results found: {len(event.actions.tool_results)}")
                    for j, tr in enumerate(event.actions.tool_results):
                        if hasattr(tr, 'response') and isinstance(tr.response, dict):
                            tr_keys = list(tr.response.keys())
                            logger.info(f"         Result {j} keys: {tr_keys}")
                            if 'slides_export_result' in tr_keys or 'status' in tr_keys:
                                logger.info(f"         ✅✅✅ Found export-related data in tool_result {j}")
                                logger.info(f"            Full response: {tr.response}")
                        else:
                            logger.info(f"         Result {j}: {type(tr.response).__name__ if hasattr(tr, 'response') else 'No response'}")
                
                # Check content.parts for tool calls
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        try:
                            for part_idx, part in enumerate(event.content.parts):
                                if hasattr(part, 'function_call'):
                                    func_name = getattr(part.function_call, 'name', 'Unknown')
                                    logger.info(f"      Part {part_idx}: function_call={func_name}")
                                if hasattr(part, 'function_response'):
                                    logger.info(f"      Part {part_idx}: function_response found")
                                    if hasattr(part.function_response, 'response'):
                                        resp = part.function_response.response
                                        if isinstance(resp, dict):
                                            logger.info(f"         Response keys: {list(resp.keys())}")
                        except Exception as e:
                            logger.debug(f"      Error checking content.parts: {e}")
            
            # Summary of SlidesExportAgent events
            if slides_export_events:
                logger.info(f"✅ Found {len(slides_export_events)} SlidesExportAgent event(s) at indices: {slides_export_events}")
            else:
                logger.warning(f"⚠️ NO SlidesExportAgent events found in {len(events)} total events!")
            
            # Extract outputs from events (ADK stores outputs in events, not automatically in session.state)
            logger.info("🔍 Extracting outputs from events...")
            report_knowledge = extract_output_from_events(events, "report_knowledge")
            presentation_outline = extract_output_from_events(events, "presentation_outline")
            slide_and_script = extract_output_from_events(events, "slide_and_script")
            slides_export_result = extract_output_from_events(events, "slides_export_result")
            
            # Update session.state with extracted outputs
            outputs = {}
            if report_knowledge:
                outputs["report_knowledge"] = report_knowledge
                session.state["report_knowledge"] = report_knowledge
                logger.info("✅ Extracted report_knowledge from events")
            if presentation_outline:
                outputs["presentation_outline"] = presentation_outline
                session.state["presentation_outline"] = presentation_outline
                logger.info("✅ Extracted presentation_outline from events")
            if slide_and_script:
                outputs["slide_and_script"] = slide_and_script
                session.state["slide_and_script"] = slide_and_script
                logger.info("✅ Extracted slide_and_script from events")
            if slides_export_result:
                outputs["slides_export_result"] = slides_export_result
                session.state["slides_export_result"] = slides_export_result
                logger.info("✅ Extracted slides_export_result from events")
                
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
            else:
                logger.warning("⚠️  No slides_export_result found in events - SlidesExportAgent may not have run")
            if session.state.get("layout_review"):
                outputs["layout_review"] = session.state["layout_review"]
                logger.info("✅ Found layout_review in session.state")
            
            logger.info(f"🔍 Extracted outputs: {list(outputs.keys())}")
            
            return outputs
        
        # Run async function (use get_event_loop for compatibility with nest-asyncio)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        outputs = loop.run_until_complete(run_agent())
        
        # Get logger for response handling
        logger = logging.getLogger(__name__)
        
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

