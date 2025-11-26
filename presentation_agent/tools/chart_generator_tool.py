"""
ADK Tool for generating charts using Plotly.
This tool is used by SlideAndScriptGeneratorAgent to generate chart images.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

try:
    from presentation_agent.utils.chart_generator import generate_chart_from_spec
    CHART_GENERATOR_AVAILABLE = True
except ImportError:
    CHART_GENERATOR_AVAILABLE = False
    logger.warning("⚠️  Chart generator not available. Install plotly and kaleido.")


def generate_chart_tool(
    chart_type: str,
    data: Dict[str, Any],
    title: str = "Chart",
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    width: int = 800,
    height: int = 600,
    color: Optional[str] = None,
    colors: Optional[List[str]] = None,
    highlighted_items: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Generate a chart image (PNG) as base64 string for insertion into Google Slides.
    
    This tool uses Plotly to generate professional, publication-quality charts.
    The chart is exported as a PNG image encoded in base64 format, which can be
    directly inserted into Google Slides using the Google Slides API.
    
    Args:
        chart_type: Type of chart to generate. Options:
            - "bar": Bar chart (for comparing categories)
            - "line": Line chart (for trends over time)
            - "pie": Pie chart (for proportions/percentages)
        data: Chart data. Format depends on chart_type:
            - For "bar": {"Category1": value1, "Category2": value2, ...}
            - For "line": {"Series1": [y1, y2, ...], "Series2": [y1, y2, ...], ...}
            - For "pie": {"Label1": value1, "Label2": value2, ...}
        title: Chart title (displayed at top of chart)
        x_label: X-axis label (optional, defaults based on chart_type)
        y_label: Y-axis label (optional, defaults based on chart_type)
        width: Chart width in pixels (default: 800)
        height: Chart height in pixels (default: 600)
        color: Single color for bar charts (hex code, e.g., "#7C3AED")
        colors: List of colors for line/pie charts (optional, uses default palette if not provided)
    
    Returns:
        Dictionary with:
            - "status": "success" or "error"
            - "chart_data": Base64-encoded PNG string (if successful)
            - "error": Error message (if failed)
            - "chart_type": The chart type that was generated
            - "title": The chart title
            - "width": Chart width in pixels
            - "height": Chart height in pixels
    
    Example:
        # Bar chart
        result = generate_chart_tool(
            chart_type="bar",
            data={"Model A": 85, "Model B": 92, "Model C": 78},
            title="Model Performance Comparison",
            x_label="Model",
            y_label="Accuracy (%)",
            color="#7C3AED"
        )
        
        # Line chart
        result = generate_chart_tool(
            chart_type="line",
            data={"Training": [0.5, 0.7, 0.8, 0.85], "Validation": [0.4, 0.6, 0.75, 0.82]},
            title="Model Training Progress",
            x_label="Epoch",
            y_label="Accuracy"
        )
        
        # Pie chart
        result = generate_chart_tool(
            chart_type="pie",
            data={"Category A": 40, "Category B": 35, "Category C": 25},
            title="Distribution"
        )
    """
    if not CHART_GENERATOR_AVAILABLE:
        return {
            "status": "error",
            "error": "Chart generator not available. Install plotly and kaleido: pip install plotly kaleido",
            "chart_type": chart_type,
            "title": title
        }
    
    try:
        # Build chart specification
        chart_spec = {
            "type": chart_type.lower(),
            "data": data,
            "title": title,
            "width": width,
            "height": height
        }
        
        # Add optional parameters
        if x_label:
            chart_spec["x_label"] = x_label
        if y_label:
            chart_spec["y_label"] = y_label
        if color:
            chart_spec["color"] = color
        if colors:
            chart_spec["colors"] = colors
        if highlighted_items:
            chart_spec["highlighted_items"] = highlighted_items
        
        # Generate chart
        chart_data_b64 = generate_chart_from_spec(chart_spec)
        
        if chart_data_b64:
            logger.info(f"✅ Generated {chart_type} chart: {title} ({width}x{height}px)")
            return {
                "status": "success",
                "chart_data": chart_data_b64,
                "chart_type": chart_type,
                "title": title,
                "width": width,
                "height": height,
                "error": None
            }
        else:
            return {
                "status": "error",
                "error": "Chart generation returned empty data",
                "chart_type": chart_type,
                "title": title
            }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Failed to generate chart: {error_msg}")
        return {
            "status": "error",
            "error": error_msg,
            "chart_type": chart_type,
            "title": title
        }

