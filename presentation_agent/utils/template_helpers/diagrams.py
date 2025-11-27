"""
Diagram rendering functions (flowcharts, workflows, process flows).
"""

import logging
import uuid
from typing import Dict, List, Optional
from presentation_agent.utils.template_loader import render_component, render_template, render_page_layout
from presentation_agent.utils.image_helper import get_image_url
from .constants import LayoutType
from .utils import _get_loader

logger = logging.getLogger(__name__)


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
    diagram_id = f"mermaid-{uuid.uuid4().hex[:8]}"
    
    # Return HTML with Mermaid code block
    return f'''<div class="mermaid-flowchart-container" data-mermaid-id="{diagram_id}">
<pre class="mermaid">
{mermaid_code}</pre>
</div>'''


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
                image_url = get_image_url(inp['image_keyword'], source="generative", is_logo=False)
            
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
            image_url = get_image_url(proc['image_keyword'], source="generative", is_logo=False)
        
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
                image_url = get_image_url(out['image_keyword'], source="generative", is_logo=False)
            
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
    
    return render_page_layout(LayoutType.WORKFLOW_DIAGRAM, variables, theme_colors)


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
                image_url = get_image_url(inp['image_keyword'], source="generative", is_logo=False)
            
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
            process_image_url = get_image_url(process['image_keyword'], source="generative", is_logo=False)
        
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
            output_image_url = get_image_url(output['image_keyword'], source="generative", is_logo=False)
        
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
    
    return render_page_layout(LayoutType.PROCESS_FLOW, variables, theme_colors)

