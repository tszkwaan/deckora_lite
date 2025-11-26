"""
Data table rendering functions.
"""

import logging
from typing import Dict, Any, List, Optional
from presentation_agent.utils.template_loader import render_component

logger = logging.getLogger(__name__)


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
    # Render headers - ensure headers is a list and each header is a dict
    if not isinstance(headers, list):
        logger.warning(f"⚠️  headers is not a list (got {type(headers).__name__}), using empty list")
        headers = []
    
    # Collect alignment for each column to apply to cells
    column_alignments = []
    
    header_html = ""
    for header in headers:
        # Ensure header is a dict
        if not isinstance(header, dict):
            logger.warning(f"⚠️  header is not a dict (got {type(header).__name__}), skipping. Value: {str(header)[:50]}")
            column_alignments.append('left')  # Default alignment
            continue
        
        width = header.get('width', '')
        align = header.get('align', 'left')
        text = header.get('text', '')
        column_alignments.append(align)  # Store alignment for this column
        style_attr = f' style="width: {width}; text-align: {align};"' if width else f' style="text-align: {align};"'
        header_html += f'<th{style_attr}>{text}</th>\n      '
    
    # Render rows - ensure rows is a list and each row is a list
    if not isinstance(rows, list):
        logger.warning(f"⚠️  rows is not a list (got {type(rows).__name__}), using empty list")
        rows = []
    
    rows_html = ""
    for row_idx, row in enumerate(rows):
        # Ensure row is a list
        if not isinstance(row, list):
            logger.warning(f"⚠️  row {row_idx} is not a list (got {type(row).__name__}), skipping. Value: {str(row)[:50]}")
            continue
        
        row_class = "highlight-row" if highlight_rows and row_idx in highlight_rows else ""
        rows_html += f'<tr class="{row_class}">\n        '
        for col_idx, cell in enumerate(row):
            cell_class = "highlight-cell" if highlight_columns and col_idx in highlight_columns else ""
            # Get alignment for this column (use stored alignment or default to 'left')
            cell_align = column_alignments[col_idx] if col_idx < len(column_alignments) else 'left'
            # Convert cell to string safely
            cell_text = str(cell) if cell is not None else ""
            rows_html += f'<td class="{cell_class}" style="text-align: {cell_align};">{cell_text}</td>\n        '
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

