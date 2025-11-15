"""
Style Extractor Agent.
Extracts design style configuration from images (Pinterest, custom uploads, etc.).
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from config import RETRY_CONFIG, DEFAULT_MODEL


def create_style_extractor_agent():
    """
    Create the Style Extractor Agent.
    
    This agent analyzes images to extract design style keywords and configuration
    for presentation slide generation.
    """
    return LlmAgent(
        name="StyleExtractorAgent",
        model=Gemini(
            model=DEFAULT_MODEL,
            retry_options=RETRY_CONFIG,
        ),
        instruction="""You are the Style Extractor Agent.

Your role is to analyze images and extract design style configuration for presentation slides.

------------------------------------------------------------
OBJECTIVES
------------------------------------------------------------

1. Analyze provided images (Pinterest selections, custom uploads, etc.)
2. Extract design style keywords and characteristics
3. Generate a structured design style configuration
4. Consider color schemes, typography preferences, layout styles, visual elements

------------------------------------------------------------
INPUTS YOU WILL RECEIVE
------------------------------------------------------------

You will be given (via state/context):
- style_images: List of image URLs or base64 encoded images
- scenario: Presentation scenario (may influence style recommendations)
- custom_instruction: Any style-related custom instructions

------------------------------------------------------------
REQUIRED OUTPUT FORMAT
------------------------------------------------------------

Respond with only valid JSON in the following structure:

{
  "color_scheme": {
    "primary_colors": ["<color1>", "<color2>"],
    "secondary_colors": ["<color1>", "<color2>"],
    "accent_colors": ["<color1>"],
    "background_style": "<light | dark | gradient | minimal>"
  },
  "typography": {
    "heading_font_style": "<modern | classic | bold | elegant>",
    "body_font_style": "<clean | readable | minimal>",
    "font_size_preference": "<large | medium | small>"
  },
  "layout_style": {
    "slide_density": "<minimal | balanced | information_dense>",
    "content_alignment": "<centered | left_aligned | mixed>",
    "visual_hierarchy": "<strong | moderate | subtle>"
  },
  "visual_elements": {
    "use_icons": true,
    "use_images": true,
    "use_charts": true,
    "decorative_elements": "<minimal | moderate | rich>"
  },
  "style_keywords": [
    "<keyword1>",
    "<keyword2>",
    "<keyword3>"
  ],
  "overall_theme": "<professional | creative | academic | modern | minimalist | etc.>"
}

If images are not provided or cannot be analyzed, infer reasonable defaults based on scenario.

------------------------------------------------------------
STYLE REQUIREMENTS
------------------------------------------------------------

- Be specific about color choices (use color names or hex codes if possible)
- Consider the presentation scenario when making recommendations
- Output must be valid JSON without additional explanations.

""",
        tools=[],  # TODO: Add image analysis tools if needed
        output_key="design_style_config",
    )

