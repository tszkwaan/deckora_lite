"""
Helper functions for rendering templates with complex logic.
These handle conditional rendering, arrays, and nested components.
"""

import logging
from typing import Dict, Any, List, Optional
from .template_loader import render_component, render_template
from .image_helper import get_image_url

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
        image_url = _get_image_from_cache_or_generate(section_data['image_keyword'], image_cache)
        icon_html = f'<img src="{image_url}" class="section-icon" alt="{section_data.get("title", "")}" />'
    elif section_data.get('image'):
        # Legacy support: if image is a URL, use it; otherwise treat as keyword
        if section_data['image'].startswith('http'):
            icon_html = f'<img src="{section_data["image"]}" class="section-icon" alt="{section_data.get("title", "")}" />'
        else:
            image_url = _get_image_from_cache_or_generate(section_data['image'], image_cache)
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
    Render a flowchart component using Mermaid.js syntax.
    
    Args:
        steps: List of step dicts with 'label' and 'description'
        theme_colors: Optional theme colors (for future use with Mermaid themes)
        orientation: 'horizontal' or 'vertical' (Mermaid handles this automatically)
        style: Flowchart style (default, minimal, detailed) - not used with Mermaid
        
    Returns:
        HTML string with Mermaid diagram code
    """
    if not steps:
        return '<div class="mermaid-flowchart-placeholder">No flowchart steps provided</div>'
    
    # Generate Mermaid flowchart syntax
    # Format: flowchart LR (left-right) or TD (top-down)
    direction = "LR" if orientation == "horizontal" else "TD"
    
    # Build Mermaid diagram code
    mermaid_code = f"flowchart {direction}\n"
    
    # Create nodes with IDs and labels
    # Use step index as node ID, sanitize labels for Mermaid
    node_ids = []
    for i, step in enumerate(steps):
        label = step.get('label', f'Step {i+1}')
        description = step.get('description', '')
        
        # Sanitize for Mermaid (remove special chars, limit length)
        node_id = f"step{i+1}"
        node_ids.append(node_id)
        
        # Combine label and description for node text
        # Mermaid supports line breaks with <br/> or \n
        if description:
            node_text = f"{label}<br/>{description}"
        else:
            node_text = label
        
        # Escape quotes and special characters
        node_text = node_text.replace('"', '&quot;').replace("'", "&apos;")
        
        # Add node definition
        mermaid_code += f'    {node_id}["{node_text}"]\n'
    
    # Add edges (arrows) between nodes
    for i in range(len(node_ids) - 1):
        mermaid_code += f"    {node_ids[i]} --> {node_ids[i+1]}\n"
    
    # Wrap in Mermaid div with unique ID
    import uuid
    diagram_id = f"mermaid-{uuid.uuid4().hex[:8]}"
    
    # Return HTML with Mermaid code block
    return f'''<div class="mermaid-flowchart-container" data-mermaid-id="{diagram_id}">
<pre class="mermaid">
{mermaid_code}</pre>
</div>'''


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
        image_url = _get_image_from_cache_or_generate(image_keyword, image_cache)
        icon_html = f'<img src="{image_url}" class="feature-icon" alt="{title}" />'
    elif image:
        # If image is a URL, use it; otherwise treat as keyword
        if image.startswith('http'):
            icon_html = f'<img src="{image}" class="feature-icon" alt="{title}" />'
        else:
            image_url = _get_image_from_cache_or_generate(image, image_cache)
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
            image_url = _get_image_from_cache_or_generate(item['image_keyword'], image_cache)
        elif not image_url and item.get('image'):
            if item['image'].startswith('http'):
                image_url = item['image']
            else:
                image_url = _get_image_from_cache_or_generate(item['image'], image_cache)
        
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
    
    return render_template('icon-row', variables, theme_colors)


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
            image_url = _get_image_from_cache_or_generate(item['image_keyword'], image_cache)
        elif not image_url and item.get('image'):
            if item['image'].startswith('http'):
                image_url = item['image']
            else:
                image_url = _get_image_from_cache_or_generate(item['image'], image_cache)
        
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
    
    return render_template('icon-sequence', variables, theme_colors)


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
            image_url = _get_image_from_cache_or_generate(step['image_keyword'], image_cache)
        elif not image_url and step.get('image'):
            if step['image'].startswith('http'):
                image_url = step['image']
            else:
                image_url = _get_image_from_cache_or_generate(step['image'], image_cache)
        
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
    
    return render_template('linear-process', variables, theme_colors)


def render_workflow_diagram_html(
    title: str,
    workflow: Dict,
    theme_colors: Optional[Dict] = None,
    subtitle: Optional[str] = None,
    evaluation_criteria: Optional[List[str]] = None,
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render a workflow-diagram layout with inputs, processes, and outputs.
    
    Args:
        title: Slide title
        workflow: Dict with 'inputs', 'processes', 'outputs', and 'connections'
        theme_colors: Optional theme colors
        subtitle: Optional subtitle text
        evaluation_criteria: Optional list of evaluation criteria strings
        
    Returns:
        Rendered HTML string
    """
    loader = _get_loader()
    
    # Build workflow HTML
    workflow_html = ""
    
    # Render inputs
    inputs = workflow.get('inputs', [])
    if inputs:
        inputs_html = ""
        for inp in inputs:
            image_url = inp.get('image_url')
            if not image_url and inp.get('image_keyword'):
                image_url = _get_image_from_cache_or_generate(inp['image_keyword'], image_cache)
            
            icon_html = f'<img src="{image_url}" alt="{inp.get("label", "")}" />' if image_url else ''
            label = inp.get('label', '')
            box_type = inp.get('type', 'input')
            
            variables = {
                'type': box_type,
                'icon_html': icon_html,
                'label': label,
                'note_html': ''
            }
            inputs_html += render_component('workflow-box', variables, theme_colors)
        
        workflow_html += f'<div class="workflow-row">{inputs_html}</div>'
    
    # Render processes
    processes = workflow.get('processes', [])
    for proc in processes:
        image_url = proc.get('image_url')
        if not image_url and proc.get('image_keyword'):
            image_url = _get_image_from_cache_or_generate(proc['image_keyword'], image_cache)
        
        icon_html = f'<img src="{image_url}" alt="{proc.get("label", "")}" />' if image_url else ''
        label = proc.get('label', '')
        
        variables = {
            'type': 'process',
            'icon_html': icon_html,
            'label': label,
            'note_html': ''
        }
        proc_html = render_component('workflow-box', variables, theme_colors)
        workflow_html += f'<div class="workflow-arrow">→</div>{proc_html}'
    
    # Render outputs
    outputs = workflow.get('outputs', [])
    if outputs:
        outputs_html = ""
        for out in outputs:
            image_url = out.get('image_url')
            if not image_url and out.get('image_keyword'):
                image_url = _get_image_from_cache_or_generate(out['image_keyword'], image_cache)
            
            icon_html = f'<img src="{image_url}" alt="{out.get("label", "")}" />' if image_url else ''
            label = out.get('label', '')
            note = out.get('note', '')
            note_html = f'<div class="workflow-box-note">{note}</div>' if note else ''
            
            variables = {
                'type': 'output',
                'icon_html': icon_html,
                'label': label,
                'note_html': note_html
            }
            outputs_html += render_component('workflow-box', variables, theme_colors)
        
        workflow_html += f'<div class="workflow-arrow">→</div><div class="workflow-row">{outputs_html}</div>'
    
    # Build evaluation criteria HTML
    evaluation_criteria_html = ""
    if evaluation_criteria:
        criteria_list = "".join([f'<li>{criteria}</li>' for criteria in evaluation_criteria])
        evaluation_criteria_html = f'''
        <div class="evaluation-criteria-list">
            <h4>Evaluation Criteria</h4>
            <ul>{criteria_list}</ul>
        </div>'''
    
    # Build subtitle HTML
    subtitle_html = f'<p class="slide-subtitle">{subtitle}</p>' if subtitle else ''
    
    # Render page layout
    variables = {
        'title': title,
        'subtitle_html': subtitle_html,
        'workflow_html': workflow_html,
        'evaluation_criteria_html': evaluation_criteria_html
    }
    
    return render_template('workflow-diagram', variables, theme_colors)


def render_process_flow_html(
    title: str,
    flow_stages: List[Dict],
    theme_colors: Optional[Dict] = None,
    section_header: Optional[str] = None,
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render a process-flow layout with multiple stages.
    
    Args:
        title: Slide title
        flow_stages: List of stage dicts with 'stage', 'title', 'inputs', 'process', 'output'
        theme_colors: Optional theme colors
        section_header: Optional section header text
        
    Returns:
        Rendered HTML string
    """
    loader = _get_loader()
    
    # Build flow stages HTML
    flow_stages_html = ""
    for i, stage in enumerate(flow_stages):
        stage_num = stage.get('stage', i + 1)
        stage_title = stage.get('title', f'Stage {stage_num}')
        
        # Build inputs HTML
        inputs_html = ""
        inputs = stage.get('inputs', [])
        for inp in inputs:
            image_url = inp.get('image_url')
            if not image_url and inp.get('image_keyword'):
                image_url = _get_image_from_cache_or_generate(inp['image_keyword'], image_cache)
            
            icon_html = f'<img src="{image_url}" alt="{inp.get("label", "")}" />' if image_url else ''
            label = inp.get('label', '')
            
            variables = {
                'type': 'input',
                'icon_html': icon_html,
                'label': label,
                'note_html': ''
            }
            inputs_html += render_component('workflow-box', variables, theme_colors)
        
        # Build process HTML
        process = stage.get('process', {})
        process_image_url = process.get('image_url')
        if not process_image_url and process.get('image_keyword'):
            process_image_url = _get_image_from_cache_or_generate(process['image_keyword'], image_cache)
        
        process_icon_html = f'<img src="{process_image_url}" alt="{process.get("label", "")}" />' if process_image_url else ''
        process_label = process.get('label', '')
        
        process_variables = {
            'type': 'process',
            'icon_html': process_icon_html,
            'label': process_label,
            'note_html': ''
        }
        process_html = render_component('workflow-box', process_variables, theme_colors)
        
        # Build output HTML
        output = stage.get('output', {})
        output_image_url = output.get('image_url')
        if not output_image_url and output.get('image_keyword'):
            output_image_url = _get_image_from_cache_or_generate(output['image_keyword'], image_cache)
        
        output_icon_html = f'<img src="{output_image_url}" alt="{output.get("label", "")}" />' if output_image_url else ''
        output_label = output.get('label', '')
        
        output_variables = {
            'type': 'output',
            'icon_html': output_icon_html,
            'label': output_label,
            'note_html': ''
        }
        output_html = render_component('workflow-box', output_variables, theme_colors)
        
        # Build stage HTML
        stage_html = f'''
        <div class="process-flow-stage">
            <div class="process-flow-stage-title">{stage_num}. {stage_title}</div>
            <div class="process-flow-stage-content">
                {inputs_html}
                <div class="process-flow-stage-arrow">→</div>
                {process_html}
                <div class="process-flow-stage-arrow">→</div>
                {output_html}
            </div>
        </div>'''
        flow_stages_html += stage_html
    
    # Build section header HTML
    section_header_html = f'<h3 class="section-header">{section_header}</h3>' if section_header else ''
    
    # Render page layout
    variables = {
        'title': title,
        'section_header_html': section_header_html,
        'flow_stages_html': flow_stages_html
    }
    
    return render_template('process-flow', variables, theme_colors)

