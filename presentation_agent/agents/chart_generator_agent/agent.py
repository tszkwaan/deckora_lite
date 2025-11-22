"""
Chart Generator Agent.
Specialized agent for generating chart images from chart specifications.
This agent is a Plotly expert and handles data validation, transformation, and chart generation.
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os
import logging
import json
import re

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from pathlib import Path
from presentation_agent.agents.utils.instruction_loader import load_instruction
try:
    from presentation_agent.agents.tools.chart_generator_tool import generate_chart_tool
    CHART_TOOL_AVAILABLE = True
except ImportError:
    CHART_TOOL_AVAILABLE = False
    generate_chart_tool = None
    logging.warning("⚠️  Chart generator tool not available")

logger = logging.getLogger(__name__)


def call_chart_generation_after_agent(callback_context):
    """
    After ChartGeneratorAgent runs, extract slide_deck from session.state,
    find slides with charts_needed=true, and generate chart_data for each.
    
    This bypasses ADK's tool calling mechanism to ensure reliable chart generation.
    """
    logger.info("📊 ChartGeneratorAgent AFTER callback - generating charts...")
    
    try:
        # Get slide_deck from session.state
        slide_deck = None
        
        # Priority 1: Try to get from session.state['slide_deck']
        if hasattr(callback_context, 'state'):
            try:
                if hasattr(callback_context.state, '__dict__'):
                    state_dict = callback_context.state.__dict__
                    slide_deck = state_dict.get('slide_deck')
                elif hasattr(callback_context.state, 'get'):
                    slide_deck = callback_context.state.get('slide_deck')
                else:
                    slide_deck = getattr(callback_context.state, 'slide_deck', None)
            except Exception as e:
                logger.debug(f"   Could not access slide_deck from state: {e}")
        
        # Priority 2: Try to get from slide_and_script
        if not slide_deck and hasattr(callback_context, 'state'):
            try:
                state_dict = {}
                if hasattr(callback_context.state, '__dict__'):
                    state_dict = callback_context.state.__dict__
                elif hasattr(callback_context.state, 'get'):
                    state_dict = {k: callback_context.state.get(k) for k in dir(callback_context.state) if not k.startswith('_')}
                
                slide_and_script = state_dict.get('slide_and_script')
                if isinstance(slide_and_script, dict) and 'slide_deck' in slide_and_script:
                    slide_deck = slide_and_script['slide_deck']
                    logger.info("   ✅ Found slide_deck in slide_and_script")
            except Exception as e:
                logger.debug(f"   Could not check slide_and_script: {e}")
        
        # Priority 3: Try to get from input message
        if not slide_deck and hasattr(callback_context, 'invocation_context'):
            try:
                if hasattr(callback_context.invocation_context, 'input_message'):
                    input_msg = callback_context.invocation_context.input_message
                    if hasattr(input_msg, 'parts') and input_msg.parts:
                        full_text = ""
                        for part in input_msg.parts:
                            if hasattr(part, 'text') and part.text:
                                full_text += part.text
                        
                        if full_text:
                            # Try to find JSON object with slide_deck
                            json_match = re.search(r'\{[\s\S]*?"slide_deck"[\s\S]*?\}', full_text, re.DOTALL)
                            if json_match:
                                try:
                                    parsed = json.loads(json_match.group(0))
                                    if isinstance(parsed, dict) and 'slide_deck' in parsed:
                                        slide_deck = parsed['slide_deck']
                                        logger.info("   ✅ Found slide_deck in input message")
                                except json.JSONDecodeError:
                                    pass
            except Exception as e:
                logger.debug(f"   Could not access input message: {e}")
        
        if not slide_deck:
            logger.warning("   ⚠️  slide_deck not found - cannot generate charts")
            return None
        
        # Parse if it's a string
        if isinstance(slide_deck, str):
            try:
                cleaned = slide_deck.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:].lstrip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:].lstrip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].rstrip()
                
                # Fix Python-style booleans
                cleaned = re.sub(r'\bTrue\b', 'true', cleaned)
                cleaned = re.sub(r'\bFalse\b', 'false', cleaned)
                cleaned = re.sub(r'\bNone\b', 'null', cleaned)
                # Fix invalid escape sequences
                cleaned = re.sub(r"\\'", "'", cleaned)
                
                slide_deck = json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.error(f"   ❌ Failed to parse slide_deck: {e}")
                return None
        
        if not isinstance(slide_deck, dict) or 'slides' not in slide_deck:
            logger.error("   ❌ Invalid slide_deck format")
            return None
        
        # Process each slide and generate charts
        charts_generated = 0
        charts_failed = 0
        
        for slide in slide_deck.get('slides', []):
            slide_number = slide.get('slide_number')
            visual_elements = slide.get('visual_elements', {})
            
            charts_needed = visual_elements.get('charts_needed', False)
            chart_spec = visual_elements.get('chart_spec')
            chart_data = visual_elements.get('chart_data')
            
            # Skip if chart not needed or already has data
            if not charts_needed or not chart_spec:
                continue
            
            # Skip if chart_data already exists and is valid (not placeholder)
            from presentation_agent.agents.utils.helpers import is_valid_chart_data
            if is_valid_chart_data(chart_data):
                logger.info(f"   ✅ Slide {slide_number}: Chart data already exists, skipping")
                continue
            
            # Generate chart
            logger.info(f"   📊 Generating chart for slide {slide_number}...")
            
            try:
                # Extract parameters from chart_spec
                chart_type = chart_spec.get('chart_type', 'bar')
                data = chart_spec.get('data', {})
                title = chart_spec.get('title', 'Chart')
                x_label = chart_spec.get('x_label')
                y_label = chart_spec.get('y_label')
                width = chart_spec.get('width', 800)
                height = chart_spec.get('height', 600)
                color = chart_spec.get('color')
                colors = chart_spec.get('colors')
                
                # Validate data
                if not data or len(data) == 0:
                    logger.warning(f"   ⚠️  Slide {slide_number}: Empty data in chart_spec")
                    charts_failed += 1
                    continue
                
                # Call the tool to generate the chart
                if not CHART_TOOL_AVAILABLE:
                    logger.error(f"   ❌ Slide {slide_number}: Chart tool not available")
                    charts_failed += 1
                    continue
                
                result = generate_chart_tool(
                    chart_type=chart_type,
                    data=data,
                    title=title,
                    x_label=x_label,
                    y_label=y_label,
                    width=width,
                    height=height,
                    color=color,
                    colors=colors
                )
                
                if result.get('status') == 'success' and result.get('chart_data'):
                    chart_data = result.get('chart_data')
                    # Update slide_deck with generated chart_data
                    visual_elements['chart_data'] = chart_data
                    slide['visual_elements'] = visual_elements
                    charts_generated += 1
                    logger.info(f"   ✅ Slide {slide_number}: Chart generated successfully (base64 length: {len(chart_data)})")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.warning(f"   ⚠️  Slide {slide_number}: Chart generation failed: {error_msg}")
                    charts_failed += 1
                    
            except Exception as e:
                import traceback
                logger.error(f"   ❌ Slide {slide_number}: Error generating chart: {e}\n{traceback.format_exc()}")
                charts_failed += 1
        
        # Update session.state with modified slide_deck
        if hasattr(callback_context, 'state'):
            try:
                if hasattr(callback_context.state, '__dict__'):
                    callback_context.state.__dict__['slide_deck'] = slide_deck
                elif hasattr(callback_context.state, '__setitem__'):
                    callback_context.state['slide_deck'] = slide_deck
                else:
                    setattr(callback_context.state, 'slide_deck', slide_deck)
                
                # Also update slide_and_script if it exists
                slide_and_script = None
                if hasattr(callback_context.state, '__dict__'):
                    slide_and_script = callback_context.state.__dict__.get('slide_and_script')
                elif hasattr(callback_context.state, 'get'):
                    slide_and_script = callback_context.state.get('slide_and_script')
                
                if slide_and_script and isinstance(slide_and_script, dict):
                    slide_and_script['slide_deck'] = slide_deck
                    if hasattr(callback_context.state, '__dict__'):
                        callback_context.state.__dict__['slide_and_script'] = slide_and_script
                    elif hasattr(callback_context.state, '__setitem__'):
                        callback_context.state['slide_and_script'] = slide_and_script
                    else:
                        setattr(callback_context.state, 'slide_and_script', slide_and_script)
                
                logger.info(f"   ✅ Updated session.state with {charts_generated} generated charts")
                if charts_failed > 0:
                    logger.warning(f"   ⚠️  {charts_failed} charts failed to generate")
            except Exception as e:
                logger.error(f"   ❌ Failed to update session.state: {e}")
        
        return {
            "charts_generated": charts_generated,
            "charts_failed": charts_failed,
            "slide_deck": slide_deck
        }
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error in chart generation callback: {e}\n{traceback.format_exc()}")
        return None


# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
# Load instruction from markdown file
_agent_dir = Path(__file__).parent
_instruction = load_instruction(_agent_dir)

agent = LlmAgent(
    name="ChartGeneratorAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction=_instruction,
    tools=[],  # No tools - chart generation happens in callback
    output_key="chart_generation_status",
    after_agent_callback=call_chart_generation_after_agent,
)

