"""
Configuration file for the presentation generation pipeline.
Contains retry config, model settings, and presentation config structure.
"""

import os
from google.genai import types

# Retry configuration for API calls
RETRY_CONFIG = types.HttpRetryOptions(
    attempts=1,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

# LLM retry configuration for agent execution
# Number of times to retry LLM calls when they fail due to format issues
LLM_RETRY_COUNT = 2  # Default: 2 retries (total of 3 attempts: 1 initial + 2 retries)

# Model configuration
DEFAULT_MODEL = "gemini-2.5-flash-lite"

# ============================================================================
# Application Configuration
# ============================================================================

# Session/Application Configuration
APP_NAME = os.getenv("APP_NAME", "presentation_agent")
USER_ID = os.getenv("USER_ID", "local_user")  # Use env var for deployment (e.g., user session ID)

# Output Directory Configuration
# Use environment variable for deployment, fallback to local development path
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "presentation_agent/output")
OUTPUT_DIR_DEPLOYMENT = os.getenv("OUTPUT_DIR", "/tmp/output")  # For Cloud Run deployment
OUTPUT_DIR_IMAGES = os.path.join(OUTPUT_DIR, "generated_images")

# Default Logic Values
DEFAULT_DURATION_SECONDS = 60  # Default to 1 minute if duration cannot be parsed
DEFAULT_NUM_SLIDES = 8  # Default number of slides if outline doesn't specify

# Output File Names
TRACE_HISTORY_FILE = "trace_history.json"
OBSERVABILITY_LOG_FILE = "observability.log"
REPORT_KNOWLEDGE_FILE = "report_knowledge.json"
PRESENTATION_OUTLINE_FILE = "presentation_outline.json"
SLIDE_AND_SCRIPT_DEBUG_FILE = "slide_and_script_raw_debug.json"
SLIDE_DECK_FILE = "slide_deck.json"
PRESENTATION_SCRIPT_FILE = "presentation_script.json"
WEB_SLIDES_RESULT_FILE = "web_slides_result.json"
SLIDES_DATA_FILE = "slides_data.json"

# Log File Names
LOGGER_LOG_FILE = "logger.log"
WEB_LOG_FILE = "web.log"
TUNNEL_LOG_FILE = "tunnel.log"

# Presentation Config structure
# This represents the input configuration for the pipeline
class PresentationConfig:
    """
    Configuration object for presentation generation.
    
    Attributes:
        scenario: Type of presentation (pitching, academic, teaching, business, technical, etc.)
                  Optional - if not provided or empty, LLM will infer from report content
        duration: Presentation duration (e.g., "10 minutes", "20 minutes")
        target_audience: Target audience (C-level, colleagues, students, non-technical, etc.)
                         Optional - if not provided, LLM will infer from scenario and report content
        custom_instruction: Custom instructions (e.g., "must explain implementation in detail", "include demo")
                            Optional - if empty, will be omitted from prompts
        report_url: URL to the report PDF (optional)
        report_content: Raw text content of the report (optional, if report_url not provided)
        style_images: List of image URLs or paths for style extraction (optional)
        template_file: Path to custom template file (optional)
    """
    def __init__(
        self,
        scenario: str = "",  # Optional - if not provided or empty, LLM will infer from report content
        duration: str = "",
        target_audience: str = None,  # Optional - if not provided, LLM will infer
        custom_instruction: str = "",  # Optional - if empty, will be omitted from prompts
        report_url: str = None,
        report_content: str = None,
        style_images: list = None,
        template_file: str = None,
    ):
        self.scenario = scenario  # Can be empty - LLM will infer if not provided
        self.duration = duration
        self.target_audience = target_audience  # Can be None - LLM will infer if not provided
        self.custom_instruction = custom_instruction  # Can be empty - will be omitted from prompts if empty
        self.report_url = report_url
        self.report_content = report_content
        self.style_images = style_images or []
        self.template_file = template_file
    
    def to_dict(self):
        """Convert to dictionary for easy state management."""
        return {
            "scenario": self.scenario,
            "duration": self.duration,
            "target_audience": self.target_audience,
            "custom_instruction": self.custom_instruction,
            "report_url": self.report_url,
            "report_content": self.report_content,
            "style_images": self.style_images,
            "template_file": self.template_file,
        }

