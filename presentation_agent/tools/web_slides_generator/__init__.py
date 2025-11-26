"""
Web Slides Generator Tool.
Generates an HTML webpage with interactive slides from slide deck and presentation script.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from .image_collection import pre_generate_images
from .frontend_data import _generate_frontend_slides_data

logger = logging.getLogger(__name__)


def generate_web_slides_tool(
    slide_deck: Dict,
    presentation_script: Dict,
    config: Optional[Dict] = None,
    title: str = "Generated Presentation",
    output_path: Optional[str] = None,
    image_cache: Optional[Dict[str, list]] = None,
    keyword_usage_tracker: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Generate frontend-ready JSON format with individual slide HTML fragments for Deckora frontend.
    
    Args:
        slide_deck: Slide deck JSON with slides array
        presentation_script: Presentation script JSON
        config: Optional config dict (scenario, duration, etc.)
        title: Presentation title
        output_path: Output JSON file path (default: from config OUTPUT_DIR/SLIDES_DATA_FILE)
        image_cache: Optional pre-generated image cache
        keyword_usage_tracker: Optional keyword usage tracker for round-robin
        
    Returns:
        Dict with status, slides_data_path, and slides_data (for frontend)
    """
    try:
        # Default output path
        if output_path is None:
            from config import OUTPUT_DIR, SLIDES_DATA_FILE
            output_dir = Path(OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / SLIDES_DATA_FILE)
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract slides and script
        slides = slide_deck.get("slides", [])
        script_sections = presentation_script.get("script_sections", [])
        
        # Create script map for easy lookup
        script_map = {section.get("slide_number"): section for section in script_sections}
        
        # Use pre-generated image cache if provided, otherwise generate on-demand
        if image_cache is None:
            image_cache = {}
        if keyword_usage_tracker is None:
            keyword_usage_tracker = {}
        
        # Generate frontend-ready JSON format (pass image_cache and usage tracker for use during HTML generation)
        slides_data = _generate_frontend_slides_data(
            slides, script_map, title, config,
            image_cache=image_cache,
            keyword_usage_tracker=keyword_usage_tracker
        )
        output_path.write_text(json.dumps(slides_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        logger.info(f"✅ Frontend slides data generated: {output_path}")
        print(f"✅ Frontend slides data generated: {output_path}")
        print(f"   📊 Total slides: {len(slides_data.get('slides', []))}")
        print(f"   📦 JSON file ready for Deckora frontend integration")
        
        return {
            "status": "success",
            "slides_data_path": str(output_path.absolute()),
            "slides_data": slides_data,
            "message": "Frontend slides data generated successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating frontend slides data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to generate frontend slides data"
        }


# Export main functions for backward compatibility
__all__ = [
    'generate_web_slides_tool',
    'pre_generate_images',
]

