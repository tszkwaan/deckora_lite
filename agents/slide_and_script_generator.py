"""
Combined Slide and Script Generator Agent.
Generates both slide content and presentation script in a single call.
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from config import RETRY_CONFIG, DEFAULT_MODEL


def create_slide_and_script_generator_agent():
    """
    Create the Combined Slide and Script Generator Agent.
    
    This agent generates both:
    1. Detailed slide content (text, structure)
    2. Presentation script (detailed explanations, transitions, timing)
    
    All in a single call for better consistency and efficiency.
    """
    return LlmAgent(
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

You will be given (via state/context):
- presentation_outline: Outline from Outline Generator Agent
- report_knowledge: Structured knowledge from Report Understanding Agent
- scenario: Presentation scenario
- duration: Presentation duration (CRITICAL for script timing)
- target_audience: Target audience
- custom_instruction: Custom instructions (e.g., "keep details in speech only")

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
        output_key="slide_and_script",  # Combined output key
    )

