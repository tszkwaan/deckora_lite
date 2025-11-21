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

# Import chart generator tool
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
            if chart_data and chart_data != "PLACEHOLDER_CHART_DATA" and len(chart_data) > 100:
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
agent = LlmAgent(
    name="ChartGeneratorAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are the Chart Generator Agent. Your role is to generate chart images from chart specifications.

You are a Plotly expert with deep knowledge of:
- Data format requirements for different chart types (bar, line, pie)
- Data validation and transformation
- Chart styling and best practices

---
YOUR TASK
---

1. Read the slide_deck from your input message (from SlideAndScriptGeneratorAgent)
2. Identify slides that have `charts_needed: true` and `chart_spec` defined
3. For each such slide, validate the chart_spec and ensure data is in the correct format
4. The actual chart generation will be handled automatically by a callback function

---
INPUT FORMAT
---

Your input message contains the slide_deck JSON from SlideAndScriptGeneratorAgent:

{
  "slide_deck": {
    "slides": [
      {
        "slide_number": 4,
        "visual_elements": {
          "charts_needed": true,
          "chart_spec": {
            "chart_type": "bar",
            "data": {"Category1": 21, "Category2": 30, ...},
            "title": "Chart Title",
            "x_label": "X-axis Label",
            "y_label": "Y-axis Label",
            "width": 800,
            "height": 600,
            "color": "#7C3AED"
          },
          "chart_data": "PLACEHOLDER_CHART_DATA"  // This needs to be replaced
        }
      }
    ]
  }
}

---
DATA FORMAT REQUIREMENTS (Plotly Expert Knowledge)
---

**Bar Charts:**
- Data format: `{"Label1": value1, "Label2": value2, ...}`
- Values must be numeric (int or float)
- Labels can be strings
- Example: `{"GPT-3.5 (Base)": 21, "GPT-3.5 (Zero-shot)": 30}`

**Line Charts:**
- Data format: `{"Series1": [y1, y2, y3, ...], "Series2": [y1, y2, y3, ...], ...}`
- Each series must be a list of numeric values
- X-axis values are implicit (indices 0, 1, 2, ...)
- Example: `{"Training": [0.5, 0.7, 0.8], "Validation": [0.4, 0.6, 0.75]}`

**Pie Charts:**
- Data format: `{"Label1": value1, "Label2": value2, ...}`
- Values must be numeric (int or float)
- Values should represent proportions or percentages
- Example: `{"Category A": 40, "Category B": 35, "Category C": 25}`

---
VALIDATION RULES
---

1. **Chart Type Validation:**
   - Must be one of: "bar", "line", "pie"
   - If invalid, log error and skip

2. **Data Validation:**
   - Data must be a dictionary (for bar/pie) or dictionary of lists (for line)
   - Data must not be empty
   - All values must be numeric (int or float)
   - For line charts, all series must be lists of numeric values

3. **Required Fields:**
   - `chart_type`: Required
   - `data`: Required, must be non-empty
   - `title`: Required (can be defaulted to "Chart" if missing)
   - `width`, `height`: Optional (default: 800, 600)

4. **Optional Fields:**
   - `x_label`, `y_label`: Required for bar/line charts, not needed for pie
   - `color`: Single color for bar charts (hex code)
   - `colors`: List of colors for line/pie charts

---
OUTPUT REQUIREMENT
---

You do NOT need to generate the chart_data yourself. The callback function will handle that.

Your role is to:
1. Validate that chart_spec is correct
2. Ensure data format matches Plotly requirements
3. Return a simple confirmation message

The callback will:
- Extract slide_deck from session.state
- Find slides with charts_needed=true
- Call generate_chart_tool for each
- Update slide_deck with generated chart_data
- Save updated slide_deck back to session.state

---
OUTPUT FORMAT
---

Return a simple JSON object:

{
  "status": "ready",
  "message": "Chart specifications validated. Charts will be generated by callback.",
  "slides_with_charts": [1, 4, 5]  // List of slide numbers that need charts
}

---
CRITICAL REQUIREMENTS
---

- ✅ Validate chart_spec format before proceeding
- ✅ Check data types match Plotly requirements
- ✅ Ensure all required fields are present
- ✅ Log any validation errors clearly
- ❌ Do NOT try to generate chart_data yourself (callback handles it)
- ❌ Do NOT modify chart_spec unless data format is incorrect

""",
    tools=[],  # No tools - chart generation happens in callback
    output_key="chart_generation_status",
    after_agent_callback=call_chart_generation_after_agent,
)

