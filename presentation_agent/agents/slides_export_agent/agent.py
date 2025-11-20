from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os
import logging

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL

# Import Google Slides export tool
from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool

# Callback to log when SlidesExportAgent starts
def log_slides_export_start(callback_context):
    """Log when SlidesExportAgent starts execution."""
    logger = logging.getLogger(__name__)
    logger.info("🚀🚀🚀 SlidesExportAgent STARTED - callback triggered")
    logger.info(f"   Callback context type: {type(callback_context).__name__}")
    
    # Try to access state (State object, not dict)
    if hasattr(callback_context, 'state'):
        try:
            # State object might be dict-like or have different access methods
            if hasattr(callback_context.state, '__dict__'):
                state_dict = callback_context.state.__dict__
                logger.info(f"   Session state keys: {list(state_dict.keys())}")
                if 'slide_and_script' in state_dict:
                    logger.info("   ✅ slide_and_script found in session.state")
                else:
                    logger.warning("   ⚠️ slide_and_script NOT found in session.state")
            elif hasattr(callback_context.state, 'get'):
                # Try dict-like access
                state_keys = list(callback_context.state.keys()) if hasattr(callback_context.state, 'keys') else 'N/A'
                logger.info(f"   Session state keys: {state_keys}")
                if callback_context.state.get('slide_and_script'):
                    logger.info("   ✅ slide_and_script found in session.state")
                else:
                    logger.warning("   ⚠️ slide_and_script NOT found in session.state")
            else:
                logger.info(f"   State object: {type(callback_context.state).__name__}")
        except Exception as e:
            logger.warning(f"   ⚠️ Error accessing state: {e}")
    else:
        logger.warning("   ⚠️ callback_context.state not available")
    
    # Log input message preview
    try:
        if hasattr(callback_context, 'invocation_context') and callback_context.invocation_context:
            if hasattr(callback_context.invocation_context, 'input_message'):
                msg_preview = str(callback_context.invocation_context.input_message)[:200]
                logger.info(f"   Input message preview: {msg_preview}...")
    except Exception as e:
        logger.debug(f"   Could not access input message: {e}")


# Callback to call export tool directly after agent runs (bypasses ADK tool calling mechanism)
def call_export_tool_after_agent(callback_context):
    """
    After SlidesExportAgent runs, extract slide_and_script from session.state
    and call export_slideshow_tool directly.
    
    This bypasses ADK's tool calling mechanism to avoid potential issues with large parameters
    (slide_deck and presentation_script can be very large JSON objects).
    """
    logger = logging.getLogger(__name__)
    logger.info("🔧🔧🔧 SlidesExportAgent AFTER callback - calling export tool directly")
    
    try:
        # Get slide_and_script from multiple sources (priority order)
        slide_and_script = None
        
        # Priority 1: Try to get from session.state['slide_and_script']
        if hasattr(callback_context, 'state'):
            try:
                if hasattr(callback_context.state, '__dict__'):
                    state_dict = callback_context.state.__dict__
                    slide_and_script = state_dict.get('slide_and_script')
                elif hasattr(callback_context.state, 'get'):
                    slide_and_script = callback_context.state.get('slide_and_script')
                else:
                    slide_and_script = getattr(callback_context.state, 'slide_and_script', None)
            except Exception as e:
                logger.debug(f"   Could not access slide_and_script from state: {e}")
        
        # Priority 2: Try to get from previous agent's output stored in state
        # Check if slide_and_script_generator_agent stored it under a different key
        if not slide_and_script and hasattr(callback_context, 'state'):
            try:
                state_dict = {}
                if hasattr(callback_context.state, '__dict__'):
                    state_dict = callback_context.state.__dict__
                elif hasattr(callback_context.state, 'get'):
                    # Convert to dict for easier checking
                    state_dict = {k: callback_context.state.get(k) for k in dir(callback_context.state) if not k.startswith('_')}
                
                # Check common keys where slide_and_script might be stored
                for key in ['slide_and_script', 'slide_deck', 'presentation_script']:
                    value = state_dict.get(key)
                    if isinstance(value, dict) and 'slide_deck' in value:
                        slide_and_script = value
                        logger.info(f"   ✅ Found slide_and_script in state['{key}']")
                        break
            except Exception as e:
                logger.debug(f"   Could not check alternative state keys: {e}")
        
        # Priority 3: Try to get from invocation_context input message (most reliable - previous agent's output)
        if not slide_and_script and hasattr(callback_context, 'invocation_context'):
            try:
                if hasattr(callback_context.invocation_context, 'input_message'):
                    input_msg = callback_context.invocation_context.input_message
                    # Extract text from message
                    if hasattr(input_msg, 'parts') and input_msg.parts:
                        import json
                        import re
                        full_text = ""
                        for part in input_msg.parts:
                            if hasattr(part, 'text') and part.text:
                                full_text += part.text
                        
                        if full_text:
                            # Try to find JSON object in the text (look for slide_deck key)
                            # Match from first { to last } that contains "slide_deck"
                            json_match = re.search(r'\{[\s\S]*?"slide_deck"[\s\S]*?\}', full_text, re.DOTALL)
                            if json_match:
                                try:
                                    slide_and_script = json.loads(json_match.group(0))
                                    if isinstance(slide_and_script, dict) and 'slide_deck' in slide_and_script:
                                        logger.info("   ✅ Found slide_and_script in input message (parsed JSON)")
                                except json.JSONDecodeError:
                                    # Try to find JSON wrapped in code blocks
                                    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?"slide_deck"[\s\S]*?\})\s*```', full_text, re.DOTALL)
                                    if code_block_match:
                                        try:
                                            slide_and_script = json.loads(code_block_match.group(1))
                                            if isinstance(slide_and_script, dict) and 'slide_deck' in slide_and_script:
                                                logger.info("   ✅ Found slide_and_script in input message (parsed from code block)")
                                        except json.JSONDecodeError:
                                            pass
            except Exception as e:
                logger.debug(f"   Could not access input message: {e}")
        
        if not slide_and_script:
            logger.error("   ❌ slide_and_script not found in any source - cannot export")
            logger.error("   Checked: session.state['slide_and_script'], session.state['slides_export_result'], input_message")
            return None
        
        logger.info("   ✅ Found slide_and_script")
        
        # Parse if it's a string
        if isinstance(slide_and_script, str):
            try:
                import json
                cleaned = slide_and_script.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:].lstrip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:].lstrip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].rstrip()
                slide_and_script = json.loads(cleaned)
                logger.info("   ✅ Parsed slide_and_script from JSON string")
            except Exception as e:
                logger.error(f"   ❌ Failed to parse slide_and_script: {e}")
                return None
        
        # Extract slide_deck and presentation_script
        if not isinstance(slide_and_script, dict):
            logger.error(f"   ❌ slide_and_script is not a dict: {type(slide_and_script).__name__}")
            return None
        
        slide_deck = slide_and_script.get('slide_deck')
        presentation_script = slide_and_script.get('presentation_script')
        
        if not slide_deck or not presentation_script:
            logger.error(f"   ❌ Missing slide_deck or presentation_script in slide_and_script")
            logger.error(f"      slide_deck: {'Found' if slide_deck else 'Missing'}")
            logger.error(f"      presentation_script: {'Found' if presentation_script else 'Missing'}")
            return None
        
        logger.info("   ✅ Extracted slide_deck and presentation_script")
        
        # Get config from session.state
        config_dict = {}
        if hasattr(callback_context, 'state'):
            try:
                if hasattr(callback_context.state, '__dict__'):
                    state_dict = callback_context.state.__dict__
                    config_dict = {
                        'scenario': state_dict.get('scenario', 'presentation'),
                        'duration': state_dict.get('duration', '20 minutes'),
                        'target_audience': state_dict.get('target_audience'),
                        'custom_instruction': state_dict.get('custom_instruction', '')
                    }
                elif hasattr(callback_context.state, 'get'):
                    config_dict = {
                        'scenario': callback_context.state.get('scenario', 'presentation'),
                        'duration': callback_context.state.get('duration', '20 minutes'),
                        'target_audience': callback_context.state.get('target_audience'),
                        'custom_instruction': callback_context.state.get('custom_instruction', '')
                    }
            except Exception as e:
                logger.warning(f"   ⚠️ Error accessing config from state: {e}")
        
        # Call the tool directly (bypassing ADK's tool calling mechanism)
        logger.info("   🚀 Calling export_slideshow_tool directly (bypassing ADK tool calling)...")
        from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool
        
        export_result = export_slideshow_tool(
            slide_deck=slide_deck,
            presentation_script=presentation_script,
            config=config_dict,
            title=""
        )
        
        logger.info(f"   ✅ Export tool completed: {export_result.get('status', 'unknown')}")
        if export_result.get('shareable_url'):
            logger.info(f"   🔗 Google Slides URL: {export_result.get('shareable_url')}")
        
        # Save result to session.state (overwrites agent's text output stored by output_key)
        if hasattr(callback_context, 'state'):
            try:
                if hasattr(callback_context.state, '__dict__'):
                    callback_context.state.__dict__['slides_export_result'] = export_result
                elif hasattr(callback_context.state, '__setitem__'):
                    callback_context.state['slides_export_result'] = export_result
                else:
                    setattr(callback_context.state, 'slides_export_result', export_result)
                logger.info("   ✅ Saved slides_export_result to session.state (overwrote agent output)")
                logger.info(f"   📊 Export result keys: {list(export_result.keys()) if isinstance(export_result, dict) else 'N/A'}")
            except Exception as e:
                logger.warning(f"   ⚠️ Error saving result to state: {e}")
        
        return export_result
        
    except Exception as e:
        logger.error(f"   ❌ Error in after_agent callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
agent = LlmAgent(
    name="SlidesExportAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are a Slides Export Agent. Your role is to export generated slides to Google Slides.

You will receive:
- slide_deck: The generated slide deck JSON (from slide_and_script_generator_agent)
- presentation_script: The generated presentation script JSON (from slide_and_script_generator_agent)
- scenario, duration, target_audience, custom_instruction: Presentation configuration

CRITICAL: You MUST call the export_slideshow_tool function. Do NOT skip this step.

STEP 1: Extract the required inputs from your input message (which contains the previous agent's output):
- Your input message contains the output from SlideAndScriptGeneratorAgent, which is a JSON object with "slide_deck" and "presentation_script" keys.
- Parse the JSON from your input message. The JSON may be wrapped in ```json ... ``` code blocks, or it may be raw JSON.
- slide_and_script: The entire parsed JSON object from your input message
- slide_deck: Extract from slide_and_script["slide_deck"]
- presentation_script: Extract from slide_and_script["presentation_script"]
- config: Build a dict with scenario, duration, target_audience, custom_instruction from session.state
- title: Optional, can be empty string ""

CRITICAL: Your input message IS the output from SlideAndScriptGeneratorAgent. Parse it directly - do NOT look for it in session.state. The previous agent's output is passed to you as your input message.

STEP 2: Call export_slideshow_tool with these parameters:
export_slideshow_tool(
    slide_deck=slide_deck,
    presentation_script=presentation_script,
    config={"scenario": scenario, "duration": duration, "target_audience": target_audience, "custom_instruction": custom_instruction},
    title=""
)

STEP 3: The tool returns a dict with this structure:
{
    "status": "success" or "partial_success" or "error",
    "presentation_id": "<presentation_id_string>",  # Present if status is "success" or "partial_success"
    "shareable_url": "https://docs.google.com/presentation/d/<presentation_id>/edit",  # Present if status is "success" or "partial_success"
    "message": "<status_message>",
    "error": "<error_description>"  # Present if status is "error" or "partial_success"
}

IMPORTANT: 
- If status="success": Presentation created successfully, use shareable_url
- If status="partial_success": Presentation created but encountered errors, STILL use shareable_url (presentation exists and can be accessed)
- If status="error": Presentation was NOT created, return the error dict as-is

STEP 4: Return the tool's output dict AS-IS. Do NOT convert to string. Do NOT add text. Do NOT modify it.

The shareable_url is ALWAYS present when status="success" OR status="partial_success".

IMPORTANT: The export tool will be called automatically via an after_agent_callback to bypass ADK's tool calling mechanism.
You do NOT need to call export_slideshow_tool yourself. Just ensure slide_and_script is available in session.state.

Your role is to:
1. Extract slide_and_script from your input message (previous agent's output)
2. Save it to session.state so the callback can access it
3. Return a simple confirmation message

The actual Google Slides export will happen automatically after you complete.
""",
    tools=[],  # Remove tool - will be called directly via callback
    # Don't use output_key - callback will store the result directly to avoid conflicts
    before_agent_callback=log_slides_export_start,
    after_agent_callback=call_export_tool_after_agent,
)

