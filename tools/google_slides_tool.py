"""
Google Slides Export Tool.
A tool function that can be used by agents to export slide decks to Google Slides.
"""

from utils.google_slides_exporter import export_to_google_slides


def export_slideshow_tool(slide_deck: dict, presentation_script: dict, config: dict, title: str = "") -> dict:
    """
    Tool function to export slide deck and script to Google Slides.
    
    This tool can be used by agents to create Google Slides presentations
    from generated slide decks and presentation scripts.
    
    Args:
        slide_deck: Slide deck JSON from slide generator
        presentation_script: Script JSON from script generator
        config: Presentation configuration dict with keys:
            - scenario: Presentation scenario (e.g., "academic_teaching")
            - duration: Presentation duration (e.g., "20 minutes")
            - target_audience: Target audience (optional)
            - custom_instruction: Custom instructions (optional)
        title: Presentation title (optional, defaults to generated title based on scenario)
        
    Returns:
        Dict with keys:
            - status: "success" or "error"
            - presentation_id: Google Slides presentation ID (if success)
            - shareable_url: URL to access the presentation (if success)
            - message: Status message
            - error: Error description (if error)
            
    Example:
        >>> result = export_slideshow_tool(
        ...     slide_deck={"slides": [...]},
        ...     presentation_script={"script_sections": [...]},
        ...     config={"scenario": "academic_teaching", "duration": "20 minutes"},
        ...     title="My Presentation"
        ... )
        >>> print(result["shareable_url"])
    """
    # Create a simple config object-like structure for compatibility
    class SimpleConfig:
        def __init__(self, config_dict):
            self.scenario = config_dict.get('scenario', 'presentation')
            self.duration = config_dict.get('duration', '20 minutes')
            self.target_audience = config_dict.get('target_audience')
            self.custom_instruction = config_dict.get('custom_instruction', '')
    
    simple_config = SimpleConfig(config)
    # Use provided title or generate one from scenario
    if title and title.strip():
        presentation_title = title
    else:
        presentation_title = f"Presentation: {simple_config.scenario}"
    
    return export_to_google_slides(
        slide_deck=slide_deck,
        presentation_script=presentation_script,
        config=simple_config,
        title=presentation_title
    )

