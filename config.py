"""
Configuration file for the presentation generation pipeline.
Contains retry config, model settings, and presentation config structure.
"""

from google.genai import types

# Retry configuration for API calls
RETRY_CONFIG = types.HttpRetryOptions(
    attempts=1,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

# Model configuration
# DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Confidence score thresholds for outline quality
# Scores range from 0.0 to 1.0, where 1.0 is best
OUTLINE_HALLUCINATION_THRESHOLD = 0.8  # Minimum hallucination_check.score (higher = fewer hallucinations)
OUTLINE_SAFETY_THRESHOLD = 0.9  # Minimum safety_check.score (higher = safer)
OUTLINE_MAX_RETRY_LOOPS = 1  # Maximum number of retry attempts

# Layout review retry configuration
LAYOUT_MAX_RETRY_LOOPS = 1  # Maximum number of retry attempts for slide generation + layout review

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

