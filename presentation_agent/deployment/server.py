"""
HTTP server for Cloud Run deployment.
Provides a REST API endpoint to run the presentation generation pipeline.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

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
            
            # Extract outputs from session state
            outputs = {}
            if session.state.get("report_knowledge"):
                outputs["report_knowledge"] = session.state["report_knowledge"]
            if session.state.get("presentation_outline"):
                outputs["presentation_outline"] = session.state["presentation_outline"]
            if session.state.get("slide_and_script"):
                outputs["slide_and_script"] = session.state["slide_and_script"]
            if session.state.get("slides_export_result"):
                outputs["slides_export_result"] = session.state["slides_export_result"]
            if session.state.get("layout_review"):
                outputs["layout_review"] = session.state["layout_review"]
            
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

