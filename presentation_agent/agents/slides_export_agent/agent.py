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

# Helper function to safely access state from callback context
def _get_state_from_context(callback_context):
    """Try multiple methods to access state from callback context."""
    state = None
    
    # Method 1: Try invocation_context.state (most common in ADK)
    if hasattr(callback_context, 'invocation_context') and callback_context.invocation_context:
        if hasattr(callback_context.invocation_context, 'state'):
            state = callback_context.invocation_context.state
    
    # Method 2: Try direct state attribute
    if state is None and hasattr(callback_context, 'state'):
        state = callback_context.state
    
    # Method 3: Try session.state
    if state is None and hasattr(callback_context, 'session'):
        if hasattr(callback_context.session, 'state'):
            state = callback_context.session.state
    
    return state


# Helper function to safely get value from state
def _get_from_state(state, key, logger=None):
    """Try multiple methods to get a value from state."""
    if state is None:
        return None
    
    try:
        # Method 1: Dict-like access
        if hasattr(state, 'get'):
            value = state.get(key)
            if value is not None:
                return value
        
        # Method 2: Attribute access
        if hasattr(state, key):
            return getattr(state, key)
        
        # Method 3: __dict__ access
        if hasattr(state, '__dict__'):
            return state.__dict__.get(key)
        
        # Method 4: Direct dict access (if state is a dict)
        if isinstance(state, dict):
            return state.get(key)
            
    except Exception as e:
        if logger:
            logger.debug(f"   Error accessing state['{key}']: {e}")
    
    return None


# Helper function to extract JSON from text (handles multiple formats)
def _extract_json_from_text(text, logger=None):
    """Extract JSON object from text, handling code blocks, escaped JSON, etc."""
    import json
    import re
    
    if not text:
        return None
    
    # Try 1: Direct JSON parse (if text is pure JSON)
    try:
        parsed = json.loads(text.strip())
        if isinstance(parsed, dict) and 'slide_deck' in parsed:
            if logger:
                logger.debug("   ✅ Found JSON via direct parse")
            return parsed
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Try 2: Extract JSON from markdown code blocks (```json ... ```)
    code_block_patterns = [
        r'```json\s*(\{[\s\S]*?\})\s*```',  # ```json {...} ```
        r'```\s*(\{[\s\S]*?\})\s*```',      # ``` {...} ```
        r'```json\s*([\s\S]*?)\s*```',       # ```json ... ``` (no braces requirement)
    ]
    
    for pattern in code_block_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1).strip())
                if isinstance(parsed, dict) and 'slide_deck' in parsed:
                    if logger:
                        logger.debug(f"   ✅ Found JSON in code block (pattern: {pattern[:20]}...)")
                    return parsed
            except json.JSONDecodeError:
                continue
    
    # Try 3: Find JSON object containing "slide_deck" key (greedy match)
    # Match from first { before "slide_deck" to last } after it
    json_match = re.search(r'\{[\s\S]*?"slide_deck"[\s\S]*?\}', text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict) and 'slide_deck' in parsed:
                if logger:
                    logger.debug("   ✅ Found JSON via regex match (slide_deck key)")
                return parsed
        except json.JSONDecodeError:
            pass
    
    # Try 4: Find balanced braces containing "slide_deck"
    # This handles cases where JSON might be embedded in other text
    start_idx = text.find('"slide_deck"')
    if start_idx != -1:
        # Find opening brace before "slide_deck"
        brace_start = text.rfind('{', 0, start_idx)
        if brace_start != -1:
            # Find matching closing brace
            brace_count = 0
            for i in range(brace_start, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            json_str = text[brace_start:i+1]
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict) and 'slide_deck' in parsed:
                                if logger:
                                    logger.debug("   ✅ Found JSON via balanced brace matching")
                                return parsed
                        except json.JSONDecodeError:
                            pass
                        break
    
    return None


# Callback to log when SlidesExportAgent starts
def log_slides_export_start(callback_context):
    """Log when SlidesExportAgent starts execution."""
    logger = logging.getLogger(__name__)
    logger.info("🚀🚀🚀 SlidesExportAgent STARTED - callback triggered")
    logger.info(f"   Callback context type: {type(callback_context).__name__}")
    
    # Try to access state using multiple methods
    state = _get_state_from_context(callback_context)
    if state:
        try:
            # Log available state keys
            state_keys = []
            if hasattr(state, 'keys'):
                state_keys = list(state.keys())
            elif hasattr(state, '__dict__'):
                state_keys = [k for k in state.__dict__.keys() if not k.startswith('_')]
            elif isinstance(state, dict):
                state_keys = list(state.keys())
            
            logger.info(f"   📊 Session state keys ({len(state_keys)}): {state_keys[:10]}{'...' if len(state_keys) > 10 else ''}")
            
            # Check for slide_and_script
            slide_and_script = _get_from_state(state, 'slide_and_script', logger)
            if slide_and_script:
                logger.info("   ✅ slide_and_script found in session.state")
            else:
                logger.warning("   ⚠️ slide_and_script NOT found in session.state")
        except Exception as e:
            logger.warning(f"   ⚠️ Error accessing state: {e}")
    else:
        logger.warning("   ⚠️ Could not access state from callback context")
    
    # Log input message preview
    try:
        if hasattr(callback_context, 'invocation_context') and callback_context.invocation_context:
            if hasattr(callback_context.invocation_context, 'input_message'):
                input_msg = callback_context.invocation_context.input_message
                # Extract text from message parts
                if hasattr(input_msg, 'parts') and input_msg.parts:
                    text_parts = []
                    for part in input_msg.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        full_text = ''.join(text_parts)
                        preview = full_text[:300] + ('...' if len(full_text) > 300 else '')
                        logger.info(f"   📝 Input message preview ({len(full_text)} chars): {preview}")
                        # Check if it contains JSON
                        if '"slide_deck"' in full_text or 'slide_deck' in full_text:
                            logger.info("   ✅ Input message contains 'slide_deck' - JSON likely present")
                else:
                    msg_str = str(input_msg)[:300]
                    logger.info(f"   📝 Input message: {msg_str}...")
    except Exception as e:
        logger.debug(f"   Could not access input message: {e}")


# NOTE: This callback is DEPRECATED and kept only for backward compatibility.
# The agent now uses standard tool calling (best practice).
# This callback is no longer used but kept for reference.
def call_export_tool_after_agent_deprecated(callback_context):
    """
    After SlidesExportAgent runs, extract slide_and_script from multiple sources
    and call export_slideshow_tool directly.
    
    This bypasses ADK's tool calling mechanism to avoid potential issues with large parameters
    (slide_deck and presentation_script can be very large JSON objects).
    
    Priority order:
    1. Input message (most reliable - ADK passes previous agent's output here)
    2. session.state['slide_and_script'] (if stored by previous agent)
    3. Alternative state keys (slide_deck, presentation_script)
    """
    logger = logging.getLogger(__name__)
    logger.info("🔧🔧🔧 SlidesExportAgent AFTER callback - calling export tool directly")
    
    try:
        slide_and_script = None
        source_used = None
        
        # ========================================================================
        # PRIORITY 1: Extract from input message (most reliable for ADK orchestrator)
        # ========================================================================
        logger.info("   🔍 Priority 1: Checking input message (previous agent's output)...")
        if hasattr(callback_context, 'invocation_context') and callback_context.invocation_context:
            if hasattr(callback_context.invocation_context, 'input_message'):
                input_msg = callback_context.invocation_context.input_message
                
                # Extract text from message parts
                full_text = ""
                if hasattr(input_msg, 'parts') and input_msg.parts:
                    text_parts = []
                    for part in input_msg.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    full_text = ''.join(text_parts)
                elif hasattr(input_msg, 'text'):
                    full_text = input_msg.text
                else:
                    # Try string conversion as fallback
                    full_text = str(input_msg)
                
                if full_text:
                    logger.info(f"   📝 Input message length: {len(full_text)} characters")
                    logger.debug(f"   📝 Input message preview: {full_text[:200]}...")
                    
                    # Use improved JSON extraction
                    slide_and_script = _extract_json_from_text(full_text, logger)
                    if slide_and_script:
                        source_used = "input_message"
                        logger.info("   ✅ Found slide_and_script in input message (Priority 1)")
                        
                        # Check if it's compressed format (only slide_deck, no presentation_script)
                        if isinstance(slide_and_script, dict) and 'slide_deck' in slide_and_script and 'presentation_script' not in slide_and_script:
                            logger.info("   📦 Detected compressed format (slide_deck only) - will get presentation_script from state")
                            # Don't break here - we'll handle it later when extracting
        
        # ========================================================================
        # PRIORITY 2: Try to get from session.state['slide_and_script']
        # ========================================================================
        if not slide_and_script:
            logger.info("   🔍 Priority 2: Checking session.state['slide_and_script']...")
            state = _get_state_from_context(callback_context)
            if state:
                slide_and_script = _get_from_state(state, 'slide_and_script', logger)
                if slide_and_script:
                    source_used = "session.state['slide_and_script']"
                    logger.info("   ✅ Found slide_and_script in session.state (Priority 2)")
        
        # ========================================================================
        # PRIORITY 3: Try alternative state keys
        # ========================================================================
        if not slide_and_script:
            logger.info("   🔍 Priority 3: Checking alternative state keys...")
            state = _get_state_from_context(callback_context)
            if state:
                # Check common keys where slide_and_script might be stored
                for key in ['slide_and_script', 'slide_deck', 'presentation_script']:
                    value = _get_from_state(state, key, logger)
                    if isinstance(value, dict) and 'slide_deck' in value:
                        slide_and_script = value
                        source_used = f"session.state['{key}']"
                        logger.info(f"   ✅ Found slide_and_script in state['{key}'] (Priority 3)")
                        break
        
        # ========================================================================
        # VALIDATION: Check if we found slide_and_script
        # ========================================================================
        if not slide_and_script:
            logger.error("   ❌ slide_and_script not found in any source - cannot export")
            logger.error("   Checked sources:")
            logger.error("     1. Input message (invocation_context.input_message)")
            logger.error("     2. session.state['slide_and_script']")
            logger.error("     3. Alternative state keys (slide_deck, presentation_script)")
            
            # Debug: Log what we actually have access to
            logger.error("   🔍 DEBUG: Available context attributes:")
            logger.error(f"      - callback_context type: {type(callback_context).__name__}")
            logger.error(f"      - Has invocation_context: {hasattr(callback_context, 'invocation_context')}")
            if hasattr(callback_context, 'invocation_context') and callback_context.invocation_context:
                logger.error(f"      - Has input_message: {hasattr(callback_context.invocation_context, 'input_message')}")
            
            state = _get_state_from_context(callback_context)
            if state:
                try:
                    state_keys = []
                    if hasattr(state, 'keys'):
                        state_keys = list(state.keys())
                    elif hasattr(state, '__dict__'):
                        state_keys = [k for k in state.__dict__.keys() if not k.startswith('_')]
                    logger.error(f"      - State keys available: {state_keys}")
                except Exception as e:
                    logger.error(f"      - Error listing state keys: {e}")
            
            return None
        
        logger.info(f"   ✅ Found slide_and_script from: {source_used}")
        
        # Parse if it's a string (shouldn't happen with improved extraction, but handle it)
        if isinstance(slide_and_script, str):
            logger.info("   🔄 Parsing slide_and_script from string...")
            parsed = _extract_json_from_text(slide_and_script, logger)
            if parsed:
                slide_and_script = parsed
                logger.info("   ✅ Parsed slide_and_script from JSON string")
            else:
                logger.error(f"   ❌ Failed to parse slide_and_script from string")
                return None
        
        # Validate slide_and_script structure
        if not isinstance(slide_and_script, dict):
            logger.error(f"   ❌ slide_and_script is not a dict: {type(slide_and_script).__name__}")
            return None
        
        # Extract slide_deck and presentation_script
        # Support both full format (slide_deck + presentation_script) and compressed format (slide_deck only)
        slide_deck = slide_and_script.get('slide_deck') if slide_and_script else None
        presentation_script = slide_and_script.get('presentation_script') if slide_and_script else None
        
        # If compressed format (only slide_deck), get presentation_script from session.state
        if slide_deck and not presentation_script:
            logger.info("   📦 Compressed format detected - getting presentation_script from session.state...")
            state = _get_state_from_context(callback_context)
            if state:
                # Try to get presentation_script from session.state
                presentation_script = _get_from_state(state, 'presentation_script', logger)
                if presentation_script:
                    logger.info("   ✅ Found presentation_script in session.state['presentation_script']")
                else:
                    # Also try to get full slide_and_script from state
                    full_slide_and_script = _get_from_state(state, 'slide_and_script', logger)
                    if full_slide_and_script and isinstance(full_slide_and_script, dict):
                        presentation_script = full_slide_and_script.get('presentation_script')
                        if presentation_script:
                            logger.info("   ✅ Found presentation_script in session.state['slide_and_script']")
        
        if not slide_deck:
            logger.error(f"   ❌ Missing slide_deck")
            logger.error(f"      slide_and_script keys: {list(slide_and_script.keys()) if slide_and_script else 'None'}")
            return None
        
        if not presentation_script:
            logger.error(f"   ❌ Missing presentation_script (needed for speaker notes)")
            logger.error(f"      slide_deck: {'Found' if slide_deck else 'Missing'}")
            logger.error(f"      presentation_script: Missing")
            logger.error(f"      Checked: slide_and_script, session.state['presentation_script'], session.state['slide_and_script']")
            return None
        
        logger.info("   ✅ Extracted slide_deck and presentation_script")
        
        # Get config from session.state using helper function
        config_dict = {}
        state = _get_state_from_context(callback_context)
        if state:
            config_dict = {
                'scenario': _get_from_state(state, 'scenario', logger) or 'presentation',
                'duration': _get_from_state(state, 'duration', logger) or '20 minutes',
                'target_audience': _get_from_state(state, 'target_audience', logger),
                'custom_instruction': _get_from_state(state, 'custom_instruction', logger) or ''
            }
        else:
            logger.warning("   ⚠️ Could not access state for config, using defaults")
            config_dict = {
                'scenario': 'presentation',
                'duration': '20 minutes',
                'target_audience': None,
                'custom_instruction': ''
            }
        
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
        state = _get_state_from_context(callback_context)
        if state:
            try:
                # Try multiple methods to save to state
                if hasattr(state, '__setitem__'):
                    state['slides_export_result'] = export_result
                elif hasattr(state, '__dict__'):
                    state.__dict__['slides_export_result'] = export_result
                elif hasattr(state, 'update'):
                    state.update({'slides_export_result': export_result})
                else:
                    setattr(state, 'slides_export_result', export_result)
                logger.info("   ✅ Saved slides_export_result to session.state")
                logger.info(f"   📊 Export result keys: {list(export_result.keys()) if isinstance(export_result, dict) else 'N/A'}")
            except Exception as e:
                logger.warning(f"   ⚠️ Error saving result to state: {e}")
        else:
            logger.warning("   ⚠️ Could not access state to save export result")
        
        # Return None - ADK will try to create an Event from the return value,
        # but we've already saved the result to session.state, so we don't need to return it.
        # Returning None prevents ADK from trying to create an Event with invalid fields.
        return None
        
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
- slide_and_script: JSON object from SlideAndScriptGeneratorAgent containing:
  - slide_deck: The generated slide deck JSON
  - presentation_script: The generated presentation script JSON (required for speaker notes)
- Config values: scenario, duration, target_audience, custom_instruction (in your input message or from previous context)

CRITICAL: You MUST call the export_slideshow_tool function. Do NOT skip this step.

STEP 1: Parse your input message:
- Your input message contains the output from SlideAndScriptGeneratorAgent
- The input is a JSON object with "slide_deck" and "presentation_script" keys
- Parse the JSON from your input message (may be wrapped in ```json ... ``` or raw JSON)
- Extract:
  - slide_deck: from parsed JSON["slide_deck"]
  - presentation_script: from parsed JSON["presentation_script"]

STEP 2: Extract config values from your input message or use defaults:
- Look for config values in your input message (they may be provided separately)
- If not found, use these defaults:
  - scenario: 'presentation'
  - duration: '20 minutes'
  - target_audience: None (optional)
  - custom_instruction: '' (empty string)

STEP 3: Call export_slideshow_tool with these parameters:
export_slideshow_tool(
    slide_deck=slide_deck,
    presentation_script=presentation_script,
    config={"scenario": scenario, "duration": duration, "target_audience": target_audience, "custom_instruction": custom_instruction},
    title=""
)

STEP 4: The tool returns a dict with this structure:
{
    "status": "success" or "partial_success" or "error",
    "presentation_id": "<presentation_id_string>",  # Present if status is "success" or "partial_success"
    "shareable_url": "https://docs.google.com/presentation/d/<presentation_id>/edit",  # Present if status is "success" or "partial_success"
    "message": "<status_message>",
    "error": "<error_description>"  # Present if status is "error" or "partial_success"
}

STEP 5: Return the tool's output dict AS-IS. Do NOT convert to string. Do NOT add text. Do NOT modify it.

IMPORTANT: 
- If status="success": Presentation created successfully, use shareable_url
- If status="partial_success": Presentation created but encountered errors, STILL use shareable_url (presentation exists and can be accessed)
- If status="error": Presentation was NOT created, return the error dict as-is

The shareable_url is ALWAYS present when status="success" OR status="partial_success".

NOTE: Both slide_deck and presentation_script are required. The presentation_script is used to generate speaker notes in Google Slides.
""",
    tools=[export_slideshow_tool],  # ✅ BEST PRACTICE: Use standard tool calling mechanism
    output_key="slides_export_result",
    before_agent_callback=log_slides_export_start,  # ✅ BEST PRACTICE: Callbacks only for observability/logging
)

