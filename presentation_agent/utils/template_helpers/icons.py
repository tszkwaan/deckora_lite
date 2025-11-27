"""
Icon-related rendering functions.
"""

import logging
from typing import Dict, List, Optional
from presentation_agent.utils.template_loader import render_component, render_template, render_page_layout
from presentation_agent.utils.image_helper import get_image_url
from .constants import LayoutType
from .utils import _get_loader

logger = logging.getLogger(__name__)


def render_icon_feature_card_html(
    title: str,
    description: str,
    theme_colors: Optional[Dict] = None,
    image: Optional[str] = None,
    image_url: Optional[str] = None,
    image_keyword: Optional[str] = None,
    icon: Optional[str] = None,  # Legacy support
    icon_url: Optional[str] = None,  # Legacy support
    highlight: Optional[str] = None,
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render an icon feature card component.
    
    Args:
        title: Feature title
        description: Feature description
        theme_colors: Optional theme colors
        image: Image keyword or URL (preferred)
        image_url: Direct image URL
        image_keyword: Keyword to search for image (fetches from Storyset/Unsplash)
        icon: Icon name/emoji (legacy - use image/image_keyword instead)
        icon_url: Icon image URL (legacy - use image_url instead)
        highlight: Optional highlight text (e.g., "30%", "3x")
        
    Returns:
        Rendered HTML string
    """
    # Build icon_html (prioritize image/image_url/image_keyword over legacy icon/icon_url)
    icon_html = ""
    if image_url:
        icon_html = f'<img src="{image_url}" class="feature-icon" alt="{title}" />'
    elif image_keyword:
        # Use cache if available, otherwise generate
        image_url = get_image_url(image_keyword, source="generative", is_logo=False)
        icon_html = f'<img src="{image_url}" class="feature-icon" alt="{title}" />'
    elif image:
        # If image is a URL, use it; otherwise treat as keyword
        if image.startswith('http'):
            icon_html = f'<img src="{image}" class="feature-icon" alt="{title}" />'
        else:
            image_url = get_image_url(image, source="generative", is_logo=False)
            icon_html = f'<img src="{image_url}" class="feature-icon" alt="{title}" />'
    elif icon_url:  # Legacy support
        icon_html = f'<img src="{icon_url}" class="feature-icon" alt="{icon or title}" />'
    elif icon:  # Legacy support for emojis
        icon_html = f'<div class="feature-icon-placeholder">{icon}</div>'
    
    # Build highlight_html
    highlight_html = f'<div class="feature-highlight">{highlight}</div>' if highlight else ''
    
    variables = {
        'icon_html': icon_html,
        'highlight_html': highlight_html,
        'title': title,
        'description': description
    }
    
    return render_component('icon-feature-card', variables, theme_colors)


def render_icon_row_html(
    title: str,
    icon_items: List[Dict],
    theme_colors: Optional[Dict] = None,
    subtitle: Optional[str] = None,
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render an icon-row layout with horizontal icons and labels.
    
    Args:
        title: Slide title
        icon_items: List of dicts with 'image_keyword' or 'image_url' and 'label'
        theme_colors: Optional theme colors
        subtitle: Optional subtitle text
        
    Returns:
        Rendered HTML string
    """
    loader = _get_loader()
    
    # Default empty cache if not provided
    if image_cache is None:
        image_cache = {}
    
    # Build icon items HTML
    icon_items_html = ""
    for item in icon_items:
        # Get image URL
        image_url = item.get('image_url')
        if not image_url and item.get('image_keyword'):
            from presentation_agent.utils.image_helper import get_image_url
            image_url = get_image_url(item['image_keyword'], source="generative", is_logo=False)
        elif not image_url and item.get('image'):
            if item['image'].startswith('http'):
                image_url = item['image']
            else:
                from presentation_agent.utils.image_helper import get_image_url
                image_url = get_image_url(item['image'], source="generative", is_logo=False)
        
        icon_html = f'<img src="{image_url}" alt="{item.get("label", "")}" />' if image_url else ''
        label = item.get('label', '')
        
        variables = {
            'icon_html': icon_html,
            'label': label
        }
        icon_items_html += render_component('icon-item', variables, theme_colors)
    
    # Build subtitle HTML
    subtitle_html = f'<p class="slide-subtitle">{subtitle}</p>' if subtitle else ''
    
    # Render page layout
    variables = {
        'title': title,
        'subtitle_html': subtitle_html,
        'icon_items_html': icon_items_html
    }
    
    return render_page_layout(LayoutType.ICON_ROW, variables, theme_colors)


def render_icon_sequence_html(
    title: str,
    sequence_items: List[Dict],
    theme_colors: Optional[Dict] = None,
    goal_text: Optional[str] = None,
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render an icon-sequence layout with icons and connectors.
    
    Args:
        title: Slide title
        sequence_items: List of dicts with 'image_keyword', 'label', and optional 'connector'
        theme_colors: Optional theme colors
        goal_text: Optional goal/description text
        
    Returns:
        Rendered HTML string
    """
    loader = _get_loader()
    
    # Default empty cache if not provided
    if image_cache is None:
        image_cache = {}
    
    # Build sequence items HTML
    sequence_items_html = ""
    for i, item in enumerate(sequence_items):
        # Get image URL
        image_url = item.get('image_url')
        if not image_url and item.get('image_keyword'):
            image_url = get_image_url(item['image_keyword'], source="generative", is_logo=False)
        elif not image_url and item.get('image'):
            if item['image'].startswith('http'):
                image_url = item['image']
            else:
                image_url = get_image_url(item['image'], source="generative", is_logo=False)
        
        icon_html = f'<img src="{image_url}" alt="{item.get("label", "")}" />' if image_url else ''
        label = item.get('label', '')
        
        # Build icon item HTML
        item_html = f'''
        <div class="icon-sequence-item">
            <div class="icon-sequence-item-icon">{icon_html}</div>
            <div class="icon-sequence-item-label">{label}</div>
        </div>'''
        sequence_items_html += item_html
        
        # Add connector if not last item
        if i < len(sequence_items) - 1:
            connector = item.get('connector', 'arrow')
            connector_class = f'connector-{connector}'
            connector_html = f'<div class="sequence-connector"><div class="{connector_class}"></div></div>'
            sequence_items_html += connector_html
    
    # Build goal text HTML
    goal_text_html = f'<p class="goal-text">{goal_text}</p>' if goal_text else ''
    
    # Render page layout
    variables = {
        'title': title,
        'goal_text_html': goal_text_html,
        'sequence_items_html': sequence_items_html
    }
    
    return render_page_layout(LayoutType.ICON_SEQUENCE, variables, theme_colors)


def render_linear_process_html(
    title: str,
    process_steps: List[Dict],
    theme_colors: Optional[Dict] = None,
    section_header: Optional[str] = None,
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render a linear-process layout with numbered steps.
    
    Args:
        title: Slide title
        process_steps: List of dicts with 'step_number', 'image_keyword', and 'label'
        theme_colors: Optional theme colors
        section_header: Optional section header text
        
    Returns:
        Rendered HTML string
    """
    loader = _get_loader()
    
    # Default empty cache if not provided
    if image_cache is None:
        image_cache = {}
    
    # Build process steps HTML
    process_steps_html = ""
    for i, step in enumerate(process_steps):
        step_number = step.get('step_number', i + 1)
        
        # Get image URL
        image_url = step.get('image_url')
        if not image_url and step.get('image_keyword'):
            image_url = get_image_url(step['image_keyword'], source="generative", is_logo=False)
        elif not image_url and step.get('image'):
            if step['image'].startswith('http'):
                image_url = step['image']
            else:
                image_url = get_image_url(step['image'], source="generative", is_logo=False)
        
        icon_html = f'<img src="{image_url}" alt="{step.get("label", "")}" />' if image_url else ''
        label = step.get('label', f'Step {step_number}')
        
        # Add arrow if not last step
        arrow_html = '<div class="process-step-arrow">→</div>' if i < len(process_steps) - 1 else ''
        
        variables = {
            'step_number': step_number,
            'icon_html': icon_html,
            'label': label,
            'arrow_html': arrow_html
        }
        process_steps_html += render_component('process-step', variables, theme_colors)
    
    # Build section header HTML
    section_header_html = f'<h3 class="section-header">{section_header}</h3>' if section_header else ''
    
    # Render page layout
    variables = {
        'title': title,
        'section_header_html': section_header_html,
        'process_steps_html': process_steps_html
    }
    
    return render_page_layout(LayoutType.LINEAR_PROCESS, variables, theme_colors)

