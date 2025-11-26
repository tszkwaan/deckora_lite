"""
Frontend data generation functions.
"""

import logging
from typing import Dict, List, Optional
from .css_generation import _generate_global_css, _generate_slide_css
from .slide_generation import _generate_slide_html_fragment
from .utils import _get_theme_colors

logger = logging.getLogger(__name__)


def _generate_frontend_slides_data(
    slides: list,
    script_map: Dict,
    title: str,
    config: Optional[Dict],
    theme_colors: Optional[Dict] = None,
    image_cache: Optional[Dict] = None,
    keyword_usage_tracker: Optional[Dict] = None
) -> Dict:
    """
    Generate frontend-ready JSON format with individual slide HTML fragments.
    
    Returns:
        Dict with:
        - metadata: Basic config (title, total_slides, scenario, etc.)
        - slides: Array of slide objects, each with:
          - slide_number: int
          - html: HTML fragment for this slide
          - css: CSS styles needed for this slide
          - design_spec: Design specifications
          - speaker_notes: Notes for this slide
          - script: Script content for this slide
    """
    # Get theme colors (use provided or get from config)
    if theme_colors is None:
        theme_colors = _get_theme_colors(config)
    global_css = _generate_global_css(theme_colors)
    
    # Default empty cache if not provided
    if image_cache is None:
        image_cache = {}
    if keyword_usage_tracker is None:
        keyword_usage_tracker = {}
    
    slides_data = []
    for idx, slide in enumerate(slides):
        slide_number = slide.get("slide_number", idx + 1)
        script_section = script_map.get(slide_number)
        
        # Generate HTML fragment for this slide only (pass image_cache and usage tracker)
        slide_html = _generate_slide_html_fragment(
            slide, script_section, idx, theme_colors,
            config=config, image_cache=image_cache,
            keyword_usage_tracker=keyword_usage_tracker
        )
        
        # Extract slide-specific CSS (if any)
        slide_css = _generate_slide_css(slide, theme_colors)
        
        # Extract visual elements for chart information
        visual_elements = slide.get("visual_elements", {})
        chart_spec = visual_elements.get("chart_spec")
        charts_needed = visual_elements.get("charts_needed", False)
        
        slide_data = {
            "slide_number": slide_number,
            "html": slide_html,
            "css": slide_css,
            "design_spec": slide.get("design_spec", {}),
            "speaker_notes": slide.get("speaker_notes", ""),
            "script": script_section if script_section else None,
            "title": slide.get("title", ""),
            "has_icons": bool(visual_elements.get("icons_fetched")),
            # Chart configuration for frontend to generate charts
            "charts_needed": charts_needed,
            "chart_spec": chart_spec if chart_spec else None
        }
        slides_data.append(slide_data)
    
    return {
        "metadata": {
            "title": title,
            "total_slides": len(slides),
            "scenario": config.get("scenario", "") if isinstance(config, dict) else "",
            "duration": config.get("duration", "") if isinstance(config, dict) else "",
            "target_audience": config.get("target_audience", "") if isinstance(config, dict) else "",
            "theme_colors": theme_colors
        },
        "global_css": global_css,
        "slides": slides_data
    }

