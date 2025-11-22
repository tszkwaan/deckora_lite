from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os
import logging

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from pathlib import Path
from presentation_agent.agents.utils.instruction_loader import load_instruction
from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool
from presentation_agent.core.json_parser import parse_json_robust

# Callback to log when SlidesExportAgent starts
def log_slides_export_start(callback_context):
    """Log when SlidesExportAgent starts execution."""
    logger = logging.getLogger(__name__)
    logger.info("🚀🚀🚀 SlidesExportAgent STARTED - callback triggered")
    logger.info(f"   Callback context type: {type(callback_context).__name__}")
    
    # Try to access state (State object, not dict)
    if hasattr(callback_context, 'state'):
        try:
            # Check _value and _delta (ADK state structure)
            state_info = []
            if hasattr(callback_context.state, '_value'):
                if isinstance(callback_context.state._value, dict):
                    state_info.append(f"_value keys: {list(callback_context.state._value.keys())}")
                    if 'slide_and_script' in callback_context.state._value:
                        logger.info("   ✅ slide_and_script found in state._value")
                else:
                    state_info.append(f"_value type: {type(callback_context.state._value).__name__}")
            
            if hasattr(callback_context.state, '_delta'):
                if isinstance(callback_context.state._delta, dict):
                    state_info.append(f"_delta keys: {list(callback_context.state._delta.keys())}")
                    if 'slide_and_script' in callback_context.state._delta:
                        logger.info("   ✅ slide_and_script found in state._delta")
                else:
                    state_info.append(f"_delta type: {type(callback_context.state._delta).__name__}")
            
            # Try dict-like access
            if hasattr(callback_context.state, 'get'):
                try:
                    state_keys = list(callback_context.state.keys()) if hasattr(callback_context.state, 'keys') else []
                    state_info.append(f"Direct keys: {state_keys}")
                    if callback_context.state.get('slide_and_script'):
                        logger.info("   ✅ slide_and_script found via state.get()")
                except:
                    pass
            
            # Try __dict__ access
            if hasattr(callback_context.state, '__dict__'):
                state_dict = callback_context.state.__dict__
                state_info.append(f"__dict__ keys: {list(state_dict.keys())}")
                if 'slide_and_script' in state_dict:
                    logger.info("   ✅ slide_and_script found in state.__dict__")
            
            if state_info:
                logger.info(f"   Session state info: {'; '.join(state_info)}")
            else:
                logger.info(f"   State object type: {type(callback_context.state).__name__}")
            
            # Final check
            if not any([
                (hasattr(callback_context.state, '_value') and isinstance(callback_context.state._value, dict) and 'slide_and_script' in callback_context.state._value),
                (hasattr(callback_context.state, '_delta') and isinstance(callback_context.state._delta, dict) and 'slide_and_script' in callback_context.state._delta),
                (hasattr(callback_context.state, 'get') and callback_context.state.get('slide_and_script')),
                (hasattr(callback_context.state, '__dict__') and 'slide_and_script' in callback_context.state.__dict__),
            ]):
                logger.warning("   ⚠️ slide_and_script NOT found in session.state")
                
        except Exception as e:
            logger.warning(f"   ⚠️ Error accessing state: {e}")
            import traceback
            logger.debug(traceback.format_exc())
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
        # ADK state object may have _value and _delta attributes
        if hasattr(callback_context, 'state'):
            try:
                # Try direct dict-like access first
                if hasattr(callback_context.state, 'get'):
                    slide_and_script = callback_context.state.get('slide_and_script')
                elif hasattr(callback_context.state, '__getitem__'):
                    try:
                        slide_and_script = callback_context.state['slide_and_script']
                    except (KeyError, TypeError):
                        slide_and_script = None
                else:
                    slide_and_script = getattr(callback_context.state, 'slide_and_script', None)
                
                # If not found, check _value attribute (ADK state structure)
                if not slide_and_script and hasattr(callback_context.state, '_value'):
                    if isinstance(callback_context.state._value, dict):
                        slide_and_script = callback_context.state._value.get('slide_and_script')
                        if slide_and_script:
                            logger.info("   ✅ Found slide_and_script in state._value")
                
                # Also check _delta (recent changes)
                if not slide_and_script and hasattr(callback_context.state, '_delta'):
                    if isinstance(callback_context.state._delta, dict):
                        slide_and_script = callback_context.state._delta.get('slide_and_script')
                        if slide_and_script:
                            logger.info("   ✅ Found slide_and_script in state._delta")
                
                # Try __dict__ access as last resort
                if not slide_and_script and hasattr(callback_context.state, '__dict__'):
                    state_dict = callback_context.state.__dict__
                    # Check both direct and in _value/_delta
                    slide_and_script = state_dict.get('slide_and_script')
                    if not slide_and_script and '_value' in state_dict:
                        if isinstance(state_dict['_value'], dict):
                            slide_and_script = state_dict['_value'].get('slide_and_script')
                    if not slide_and_script and '_delta' in state_dict:
                        if isinstance(state_dict['_delta'], dict):
                            slide_and_script = state_dict['_delta'].get('slide_and_script')
                            
            except Exception as e:
                logger.debug(f"   Could not access slide_and_script from state: {e}")
        
        # Priority 2: Try to get from previous agent's output stored in state under different keys
        # Check if slide_and_script_generator_agent stored it under a different key
        if not slide_and_script and hasattr(callback_context, 'state'):
            try:
                # Helper function to get value from state
                def get_from_state(key):
                    if hasattr(callback_context.state, 'get'):
                        return callback_context.state.get(key)
                    elif hasattr(callback_context.state, '__getitem__'):
                        try:
                            return callback_context.state[key]
                        except (KeyError, TypeError):
                            return None
                    elif hasattr(callback_context.state, '_value') and isinstance(callback_context.state._value, dict):
                        return callback_context.state._value.get(key)
                    elif hasattr(callback_context.state, '_delta') and isinstance(callback_context.state._delta, dict):
                        return callback_context.state._delta.get(key)
                    else:
                        return getattr(callback_context.state, key, None)
                
                # Check common keys where slide_and_script might be stored
                for key in ['slide_and_script', 'slide_deck', 'presentation_script']:
                    value = get_from_state(key)
                    if isinstance(value, dict) and 'slide_deck' in value:
                        slide_and_script = value
                        logger.info(f"   ✅ Found slide_and_script in state['{key}']")
                        break
                    # Also check if slide_deck and presentation_script are separate
                    if key == 'slide_deck' and value and not slide_and_script:
                        script_value = get_from_state('presentation_script')
                        if script_value:
                            slide_and_script = {
                                'slide_deck': value,
                                'presentation_script': script_value
                            }
                            logger.info(f"   ✅ Constructed slide_and_script from separate slide_deck and presentation_script")
                            break
            except Exception as e:
                logger.debug(f"   Could not check alternative state keys: {e}")
        
        # Priority 3: Try to get from invocation_context input message (MOST RELIABLE - previous agent's output)
        # In SequentialAgent/LoopAgent, previous agent's output is passed as input_message
        if not slide_and_script and hasattr(callback_context, 'invocation_context'):
            try:
                if hasattr(callback_context.invocation_context, 'input_message'):
                    input_msg = callback_context.invocation_context.input_message
                    logger.info("   🔍 Checking input_message for slide_and_script...")
                    
                    # Extract text from message
                    full_text = ""
                    if hasattr(input_msg, 'parts') and input_msg.parts:
                        for part in input_msg.parts:
                            if hasattr(part, 'text') and part.text:
                                full_text += part.text
                    elif isinstance(input_msg, str):
                        full_text = input_msg
                    elif hasattr(input_msg, '__str__'):
                        full_text = str(input_msg)
                    
                    if full_text:
                        logger.info(f"   📝 Input message length: {len(full_text)} chars")
                        logger.info(f"   📝 First 200 chars: {full_text[:200]}...")
                        
                        import json
                        import re
                        
                        # Try parse_json_robust first (handles markdown, Python booleans, etc.)
                        parsed = parse_json_robust(full_text, extract_wrapped=False)
                        if parsed and isinstance(parsed, dict) and 'slide_deck' in parsed:
                            slide_and_script = parsed
                            logger.info("   ✅ Found slide_and_script in input message (via parse_json_robust)")
                        else:
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
                import traceback
                logger.debug(traceback.format_exc())
        
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
# Load instruction from markdown file
_agent_dir = Path(__file__).parent
_instruction = load_instruction(_agent_dir)

agent = LlmAgent(
    name="SlidesExportAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction=_instruction,
    tools=[],  # Remove tool - will be called directly via callback
    # Don't use output_key - callback will store the result directly to avoid conflicts
    before_agent_callback=log_slides_export_start,
    after_agent_callback=call_export_tool_after_agent,
)

