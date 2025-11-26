"""
Template helper functions for rendering HTML components.

This module provides functions for rendering various presentation components
including comparison sections, tables, diagrams, icons, and slide layouts.

All functions are exported from their respective modules for backward compatibility.
"""

# Import all functions from their respective modules
from .comparison import (
    render_comparison_section_html,
    render_comparison_grid_html,
)
from .tables import (
    render_data_table_html,
)
from .diagrams import (
    render_flowchart_html,
    render_workflow_diagram_html,
    render_process_flow_html,
)
from .icons import (
    render_icon_feature_card_html,
    render_icon_row_html,
    render_icon_sequence_html,
    render_linear_process_html,
)
from .slides import (
    render_cover_slide_html,
    render_fancy_content_text_html,
    render_fancy_chart_html,
)
from .utils import (
    highlight_numbers_in_text,
    markdown_to_html,
)

# Export all functions for backward compatibility
__all__ = [
    # Comparison functions
    'render_comparison_section_html',
    'render_comparison_grid_html',
    # Table functions
    'render_data_table_html',
    # Diagram functions
    'render_flowchart_html',
    'render_workflow_diagram_html',
    'render_process_flow_html',
    # Icon functions
    'render_icon_feature_card_html',
    'render_icon_row_html',
    'render_icon_sequence_html',
    'render_linear_process_html',
    # Slide functions
    'render_cover_slide_html',
    'render_fancy_content_text_html',
    'render_fancy_chart_html',
    # Utility functions
    'highlight_numbers_in_text',
    'markdown_to_html',
]

