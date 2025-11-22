"""
Helper functions for rendering templates with complex logic.
These handle conditional rendering, arrays, and nested components.
"""

import logging
from typing import Dict, Any, List, Optional
from .template_loader import render_component, render_template

logger = logging.getLogger(__name__)

# Singleton loader instance
_loader = None

def _get_loader():
    global _loader
    if _loader is None:
        from .template_loader import TemplateLoader
        _loader = TemplateLoader()
    return _loader

logger = logging.getLogger(__name__)


def render_comparison_section_html(section_data: Dict, theme_colors: Optional[Dict] = None) -> str:
    """
    Render a comparison section with proper icon handling.
    
    Args:
        section_data: Dict with title, content, icon, icon_url, etc.
        theme_colors: Optional theme colors
        
    Returns:
        Rendered HTML string
    """
    # Build icon_html
    icon_html = ""
    if section_data.get('icon_url'):
        icon_html = f'<img src="{section_data["icon_url"]}" class="section-icon" alt="{section_data.get("icon", "")}" />'
    elif section_data.get('icon'):
        icon_html = f'<div class="section-icon-placeholder">{section_data["icon"]}</div>'
    
    # Add icon_html to section_data
    section_data['icon_html'] = icon_html
    
    # Handle highlight class
    if section_data.get('highlight'):
        section_data['highlight'] = 'highlighted'
    else:
        section_data['highlight'] = ''
    
    # Render the component
    return render_component('comparison-section', section_data, theme_colors)


def render_comparison_grid_html(
    title: str,
    sections: List[Dict],
    theme_colors: Optional[Dict] = None,
    title_font_size: int = 36,
    title_align: str = "left"
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
    
    # Render each section
    rendered_sections = []
    for section in sections:
        rendered_section = render_comparison_section_html(section, theme_colors)
        rendered_sections.append(rendered_section)
    
    # Prepare variables for layout template
    variables = {
        'title': title,
        'sections_html': '\n'.join(rendered_sections),
        'sections_count': len(sections),
        'title_font_size': title_font_size,
        'title_align': title_align
    }
    
    layout = _get_loader().get_page_layout('comparison-grid')
    if not layout:
        logger.error("comparison-grid layout not found")
        return f'<div class="slide-content"><h1>{title}</h1><div>Error: comparison-grid layout not found</div></div>'
    
    return render_template(layout, variables, theme_colors)


def render_data_table_html(
    headers: List[Dict[str, Any]],
    rows: List[List[str]],
    theme_colors: Optional[Dict] = None,
    style: str = "default",
    highlight_rows: Optional[List[int]] = None,
    highlight_columns: Optional[List[int]] = None,
    caption: Optional[str] = None
) -> str:
    """
    Render a data table component.
    
    Args:
        headers: List of header dicts with 'text', 'width', 'align'
        rows: List of row data arrays
        theme_colors: Optional theme colors
        style: Table style (default, striped, bordered, minimal)
        highlight_rows: Row indices to highlight
        highlight_columns: Column indices to highlight
        caption: Optional table caption
        
    Returns:
        Rendered HTML string
    """
    # Render headers
    header_html = ""
    for header in headers:
        width = header.get('width', '')
        align = header.get('align', 'left')
        text = header.get('text', '')
        style_attr = f' style="width: {width}; text-align: {align};"' if width else f' style="text-align: {align};"'
        header_html += f'<th{style_attr}>{text}</th>\n      '
    
    # Render rows
    rows_html = ""
    for row_idx, row in enumerate(rows):
        row_class = "highlight-row" if highlight_rows and row_idx in highlight_rows else ""
        rows_html += f'<tr class="{row_class}">\n        '
        for col_idx, cell in enumerate(row):
            cell_class = "highlight-cell" if highlight_columns and col_idx in highlight_columns else ""
            rows_html += f'<td class="{cell_class}">{cell}</td>\n        '
        rows_html += '</tr>\n      '
    
    # Build caption HTML
    caption_html = f'<div class="table-caption">{caption}</div>' if caption else ''
    
    variables = {
        'headers': header_html,
        'rows': rows_html,
        'style': style,
        'caption_html': caption_html
    }
    
    return render_component('data-table', variables, theme_colors)


def render_flowchart_html(
    steps: List[Dict[str, str]],
    theme_colors: Optional[Dict] = None,
    orientation: str = "horizontal",
    style: str = "default"
) -> str:
    """
    Render a flowchart component.
    
    Args:
        steps: List of step dicts with 'label' and 'description'
        theme_colors: Optional theme colors
        orientation: 'horizontal' or 'vertical'
        style: Flowchart style (default, minimal, detailed)
        
    Returns:
        Rendered HTML string
    """
    # Render steps with arrows
    steps_html = ""
    for i, step in enumerate(steps):
        label = step.get('label', '')
        description = step.get('description', '')
        steps_html += f'''<div class="flow-step">
  <div class="flow-step-label">{label}</div>
  <div class="flow-step-description">{description}</div>
</div>'''
        
        # Add arrow between steps (not after last)
        if i < len(steps) - 1:
            steps_html += '<div class="flow-arrow"></div>'
    
    variables = {
        'steps': steps_html,
        'orientation': orientation,
        'style': style
    }
    
    return render_component('flowchart', variables, theme_colors)


def render_timeline_item_html(
    year: Optional[str],
    title: str,
    description: str,
    theme_colors: Optional[Dict] = None,
    icon: Optional[str] = None,
    highlight: bool = False
) -> str:
    """
    Render a timeline item component.
    
    Args:
        year: Year or step number
        title: Item title
        description: Item description
        theme_colors: Optional theme colors
        icon: Optional icon
        highlight: Whether to highlight
        
    Returns:
        Rendered HTML string
    """
    marker = year or icon or '•'
    variables = {
        'year': marker,
        'title': title,
        'description': description,
        'highlight': 'highlighted' if highlight else ''
    }
    
    return render_component('timeline-item', variables, theme_colors)


def render_timeline_html(
    title: str,
    timeline_items: List[Dict],
    theme_colors: Optional[Dict] = None,
    title_font_size: int = 36,
    title_align: str = "left",
    orientation: str = "vertical"
) -> str:
    """
    Render a timeline layout.
    
    Args:
        title: Slide title
        timeline_items: List of timeline item dicts
        theme_colors: Optional theme colors
        title_font_size: Title font size
        title_align: Title alignment
        orientation: 'vertical' or 'horizontal'
        
    Returns:
        Rendered HTML string
    """
    # Render each timeline item
    rendered_items = []
    for item in timeline_items:
        rendered_item = render_timeline_item_html(
            item.get('year'),
            item.get('title', ''),
            item.get('description', ''),
            theme_colors,
            item.get('icon'),
            item.get('highlight', False)
        )
        rendered_items.append(rendered_item)
    
    variables = {
        'title': title,
        'timeline_items_html': '\n'.join(rendered_items),
        'title_font_size': title_font_size,
        'title_align': title_align,
        'orientation': orientation
    }
    
    layout = _get_loader().get_page_layout('timeline')
    if not layout:
        logger.error("timeline layout not found")
        return f'<div class="slide-content"><h1>{title}</h1><div>Error: timeline layout not found</div></div>'
    
    return render_template(layout, variables, theme_colors)


def render_icon_feature_card_html(
    title: str,
    description: str,
    theme_colors: Optional[Dict] = None,
    icon: Optional[str] = None,
    icon_url: Optional[str] = None,
    highlight: Optional[str] = None
) -> str:
    """
    Render an icon feature card component.
    
    Args:
        title: Feature title
        description: Feature description
        theme_colors: Optional theme colors
        icon: Icon name/emoji
        icon_url: Icon image URL
        highlight: Optional highlight text (e.g., "30%", "3x")
        
    Returns:
        Rendered HTML string
    """
    # Build icon_html
    icon_html = ""
    if icon_url:
        icon_html = f'<img src="{icon_url}" class="feature-icon" alt="{icon or ""}" />'
    elif icon:
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

