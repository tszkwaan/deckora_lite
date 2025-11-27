"""
Frontend data generation functions.
"""

import logging
from typing import Dict, List, Optional
from .css_generation import _generate_global_css, _generate_slide_css
from .slide_generation import _generate_slide_html_fragment
from .utils import _get_theme_colors, _parse_json_safely

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
        # Validate slide is a dict (handle cases where it might be a string or escaped JSON)
        if isinstance(slide, str):
            try:
                slide = _parse_json_safely(slide)
            except ValueError:
                logger.warning(f"⚠️  slide[{idx}] is a string but not valid JSON, skipping")
                continue
        if not isinstance(slide, dict):
            logger.warning(f"⚠️  slide[{idx}] is not a dict (got {type(slide).__name__}), skipping")
            continue
        
        slide_number = slide.get("slide_number", idx + 1)
        script_section = script_map.get(slide_number)
        
        try:
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
        except Exception as e:
            # Log error for this specific slide but continue with others
            logger.error(f"❌ Error generating HTML for slide {slide_number}: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            # Create a fallback slide with error message
            from .slide_generation import _get_placeholder_content
            fallback_html = f'<div class="slide-content"><h1 class="slide-title">{slide.get("title", f"Slide {slide_number}")}</h1><div class="slide-body">{_get_placeholder_content()}</div></div>'
            slide_data = {
                "slide_number": slide_number,
                "html": fallback_html,
                "css": "",
                "design_spec": slide.get("design_spec", {}),
                "speaker_notes": slide.get("speaker_notes", ""),
                "script": script_section if script_section else None,
                "title": slide.get("title", f"Slide {slide_number}"),
                "has_icons": False,
                "charts_needed": False,
                "chart_spec": None
            }
            slides_data.append(slide_data)
            logger.warning(f"⚠️  Added fallback slide {slide_number} due to generation error")
    
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

