from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os
import logging

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from presentation_agent.agents.utils.helpers import compress_layout_review

logger = logging.getLogger(__name__)


def compress_layout_review_before_agent(callback_context):
    """
    ✅ BEST PRACTICE: Context compaction - compress layout_review before passing to agent.
    This callback compresses layout_review in session.state to reduce token usage during retry.
    """
    try:
        # Try to access state from callback context
        state = None
        if hasattr(callback_context, 'invocation_context') and callback_context.invocation_context:
            if hasattr(callback_context.invocation_context, 'state'):
                state = callback_context.invocation_context.state
        
        if state is None and hasattr(callback_context, 'state'):
            state = callback_context.state
        
        if state is None and hasattr(callback_context, 'session'):
            if hasattr(callback_context.session, 'state'):
                state = callback_context.session.state
        
        if state:
            # Check if layout_review exists (indicates this is a retry)
            layout_review = None
            if hasattr(state, 'get'):
                layout_review = state.get('layout_review')
            elif hasattr(state, 'layout_review'):
                layout_review = getattr(state, 'layout_review', None)
            
            if layout_review:
                # Compress layout_review
                compressed = compress_layout_review(layout_review)
                
                # Store compressed version back to state
                if hasattr(state, '__setitem__'):
                    state['layout_review_compressed'] = compressed
                elif hasattr(state, '__setattr__'):
                    setattr(state, 'layout_review_compressed', compressed)
                
                # Log compression stats
                import json
                original_size = len(json.dumps(layout_review))
                compressed_size = len(json.dumps(compressed))
                reduction = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
                logger.info(f"📦 Context compaction (layout_review): {original_size:,} → {compressed_size:,} chars ({reduction:.1f}% reduction)")
                
    except Exception as e:
        logger.warning(f"⚠️  Could not compress layout_review in callback: {e}")

# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
agent = LlmAgent(
    name="SlideAndScriptGeneratorAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are the Combined Slide and Script Generator Agent.

Your role is to generate BOTH slide content AND presentation script in a single response.

------------------------------------------------------------
OBJECTIVES
------------------------------------------------------------

1. Read presentation_outline (from Outline Generator Agent)
2. Read report_knowledge for detailed content
3. Generate detailed slide content with text, bullet points, and structure
4. Generate a natural, conversational script that expands on slide content
5. Ensure content is appropriate for the target audience and scenario
6. Ensure script timing matches the specified duration

------------------------------------------------------------
INPUTS YOU WILL RECEIVE
------------------------------------------------------------

✅ BEST PRACTICE: Reference-based data access using ADK variable injection syntax
- All data is stored in session.state and automatically injected into your instructions
- You will receive filtered report_knowledge and presentation_outline in the message (to reduce token usage)
- Full data is available via session.state:
  - Full report_knowledge: session.state['report_knowledge']
  - Full presentation_outline: session.state['presentation_outline']
  - Configuration: session.state['scenario'], session.state['duration'], etc.

You will receive in the message:
- presentation_outline: Filtered outline (full version available via session.state['presentation_outline'])
- report_knowledge: Filtered structured knowledge (full version available via session.state['report_knowledge'])

[PREVIOUS_LAYOUT_REVIEW] (optional - only present if this is a retry)
<Compressed actionable feedback from previous layout review>
Format: {"issues": [...], "slides_to_fix": [1, 4, 5]}
[END_PREVIOUS_LAYOUT_REVIEW]

[THRESHOLD_CHECK] (optional - only present if this is a retry)
<Threshold check result indicating why regeneration is needed>
[END_THRESHOLD_CHECK]

✅ BEST PRACTICE: If [PREVIOUS_LAYOUT_REVIEW] and [THRESHOLD_CHECK] are provided, use them to improve the slides:
- Focus on the specific issues listed in the "issues" array
- Fix the slides listed in "slides_to_fix" array
- Address layout problems mentioned: text overlap, overflow, spacing issues
- Improve formatting based on the actionable feedback provided

------------------------------------------------------------
REQUIRED OUTPUT FORMAT
------------------------------------------------------------

Respond with only valid JSON in the following structure:

{
  "slide_deck": {
    "slides": [
      {
        "slide_number": 1,
        "title": "<slide title>",
        "content": {
          "main_text": "<main text or null>",
          "bullet_points": [
            "<bullet 1>",
            "<bullet 2>"
          ],
          "subheadings": [
            {
              "heading": "<subheading>",
              "content": "<content or bullet points>"
            }
          ]
        },
        "visual_elements": {
          "figures": ["<figure_id>"],
          "charts_needed": true,
          "icons_suggested": ["<icon_type1>", "<icon_type2>"]
        },
        "formatting_notes": "<notes on how to format this slide>",
        "speaker_notes": "<brief notes for the speaker about this slide>"
      }
    ],
    "slide_deck_metadata": {
      "total_slides": <number>,
      "theme": "<theme name>",
      "color_scheme_applied": true,
      "style_keywords": ["<keyword1>", "<keyword2>"]
    }
  },
  "presentation_script": {
    "script_sections": [
      {
        "slide_number": 1,
        "slide_title": "<title>",
        "opening_line": "<how to start talking about this slide>",
        "main_content": [
          {
            "point": "<point or topic>",
            "explanation": "<detailed explanation to say>",
            "estimated_time": <seconds>
          }
        ],
        "transitions": {
          "from_previous": "<transition from previous slide>",
          "to_next": "<transition to next slide>"
        },
        "key_phrases": [
          "<important phrase 1>",
          "<important phrase 2>"
        ],
        "notes": "<any special notes for this section>"
      }
    ],
    "script_metadata": {
      "total_estimated_time": "<total time in seconds or format like '60 seconds'>",
      "tone": "<professional | conversational | academic | etc.>",
      "language_level": "<appropriate for target audience>"
    },
    "opening_remarks": "<how to start the presentation>",
    "closing_remarks": "<how to conclude the presentation>"
  }
}

------------------------------------------------------------
CRITICAL REQUIREMENTS
------------------------------------------------------------

1. **Slide Content:**
   - Keep slide content concise and scannable
   - Follow custom_instruction (e.g., "point form only", "keep slides clean")
   - Ensure content depth matches audience level from report_knowledge
   - Include speaker notes that provide context not on slides

2. **Script Content:**
   - Write in a natural, conversational tone suitable for speaking
   - Expand on slide content with detailed explanations
   - Respect custom_instruction (e.g., "explain implementation in detail", "keep details in speech only")
   - Include smooth transitions between slides
   - **CRITICAL: Ensure total_estimated_time matches the specified duration**
   - Each point in main_content should have an estimated_time in seconds
   - Sum of all estimated_time values should approximately equal the target duration

3. **Consistency:**
   - The script must align with the slide content
   - Each script section should correspond to a slide
   - The number of script_sections must match the number of slides

4. **Output:**
   - Output must be valid JSON without additional explanations
   - Both slide_deck and presentation_script must be present
   - Do NOT invent any facts, numbers, or technical details not in the report_knowledge

""",
    tools=[],
    output_key="slide_and_script",
    before_agent_callback=compress_layout_review_before_agent,  # ✅ BEST PRACTICE: Compress layout_review during retry
)

