"""
Comparison section and grid rendering functions.
"""

import logging
from typing import Dict, List, Optional
from presentation_agent.utils.template_loader import render_component, render_page_layout
from presentation_agent.utils.image_helper import get_image_url
from .constants import LayoutType

logger = logging.getLogger(__name__)


def render_comparison_section_html(section_data: Dict, theme_colors: Optional[Dict] = None, image_cache: Optional[Dict] = None) -> str:
    """
    Render a comparison section with proper image handling.
    
    Args:
        section_data: Dict with title, content, image, image_url, image_keyword, etc.
        theme_colors: Optional theme colors
        image_cache: Optional pre-generated image cache (keyword -> image_url)
        
    Returns:
        Rendered HTML string
    """
    # Default empty cache if not provided
    if image_cache is None:
        image_cache = {}
    
    # Build icon_html (now supports image/image_url/image_keyword)
    icon_html = ""
    if section_data.get('image_url'):
        icon_html = f'<img src="{section_data["image_url"]}" class="section-icon" alt="{section_data.get("title", "")}" />'
    elif section_data.get('image_keyword'):
        # Use cache if available, otherwise generate
        image_url = get_image_url(section_data['image_keyword'], source="generative", is_logo=False)
        icon_html = f'<img src="{image_url}" class="section-icon" alt="{section_data.get("title", "")}" />'
    elif section_data.get('image'):
        # Legacy support: if image is a URL, use it; otherwise treat as keyword
        if section_data['image'].startswith('http'):
            icon_html = f'<img src="{section_data["image"]}" class="section-icon" alt="{section_data.get("title", "")}" />'
        else:
            image_url = get_image_url(section_data['image'], source="generative", is_logo=False)
            icon_html = f'<img src="{image_url}" class="section-icon" alt="{section_data.get("title", "")}" />'
    elif section_data.get('icon_url'):  # Legacy support
        icon_html = f'<img src="{section_data["icon_url"]}" class="section-icon" alt="{section_data.get("icon", "")}" />'
    elif section_data.get('icon'):  # Legacy support for emojis
        icon_html = f'<div class="section-icon-placeholder">{section_data["icon"]}</div>'
    
    # Handle highlight class
    highlight_class = 'highlighted' if section_data.get('highlight') else ''
    
    # Prepare variables for template (don't modify original dict)
    template_vars = {
        'title': section_data.get('title', ''),
        'content': section_data.get('content', ''),
        'background_color': section_data.get('background_color', 'transparent'),
        'icon_html': icon_html,
        'highlight': highlight_class
    }
    
    # Render the component
    return render_component('comparison-section', template_vars, theme_colors)


def render_comparison_grid_html(
    title: str,
    sections: List[Dict],
    theme_colors: Optional[Dict] = None,
    title_font_size: int = 36,
    title_align: str = "left",
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render a comparison grid layout with multiple sections.
    
    Args:
        title: Slide title
        sections: List of section data dicts (min 2, max 4)
        theme_colors: Optional theme colors
        title_font_size: Title font size
        title_align: Title alignment
        
    Returns:
        Rendered HTML string
    """
    if len(sections) < 2:
        logger.warning("comparison-grid requires at least 2 sections, got {len(sections)}")
        sections = sections[:2] if len(sections) == 1 else []
    
    if len(sections) > 4:
        logger.warning("comparison-grid supports max 4 sections, truncating to 4")
        sections = sections[:4]
    
    # Default empty cache if not provided
    if image_cache is None:
        image_cache = {}
    
    # Render each section
    rendered_sections = []
    for section in sections:
        rendered_section = render_comparison_section_html(section, theme_colors, image_cache=image_cache)
        rendered_sections.append(rendered_section)
    
    # Prepare variables for layout template
    variables = {
        'title': title,
        'sections_html': '\n'.join(rendered_sections),
        'sections_count': len(sections),
        'title_font_size': title_font_size,
        'title_align': title_align
    }
    
    # Use render_page_layout for consistency and proper error handling
    return render_page_layout(LayoutType.COMPARISON_GRID, variables, theme_colors)

