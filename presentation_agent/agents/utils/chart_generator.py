"""
Chart generation utility using Plotly.
Generates static PNG charts for insertion into Google Slides.
"""

import base64
import io
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.io import to_image
    PLOTLY_AVAILABLE = True
    # Check if kaleido is available
    try:
        import kaleido
        KALEIDO_AVAILABLE = True
    except ImportError:
        KALEIDO_AVAILABLE = False
        logger.warning("⚠️  Kaleido not installed. Chart image export may fail.")
        logger.warning("   Install with: pip install kaleido")
except ImportError:
    PLOTLY_AVAILABLE = False
    KALEIDO_AVAILABLE = False
    logger.warning("⚠️  Plotly not installed. Chart generation will be disabled.")
    logger.warning("   Install with: pip install plotly kaleido")


def generate_bar_chart(
    data: Dict[str, float],
    title: str = "Chart",
    x_label: str = "Category",
    y_label: str = "Value",
    width: int = 800,
    height: int = 600,
    color: str = "#7C3AED",
    colors: Optional[List[str]] = None,
    highlighted_items: Optional[List[str]] = None
) -> Optional[str]:
    """
    Generate a bar chart and return as base64-encoded PNG.
    
    Args:
        data: Dictionary with {label: value} pairs
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        width: Chart width in pixels
        height: Chart height in pixels
        color: Bar color (hex code) - used if colors not provided
        colors: Optional list of colors for each bar (overrides color)
        highlighted_items: Optional list of item names to highlight in brand color
    
    Returns:
        Base64-encoded PNG string, or None if Plotly is not available
    """
    if not PLOTLY_AVAILABLE:
        logger.error("❌ Plotly not available. Cannot generate chart.")
        return None
    
    # Validate data
    if not data or len(data) == 0:
        logger.error("❌ Empty data provided for bar chart")
        return None
    
    # Ensure all values are numeric
    try:
        data = {k: float(v) for k, v in data.items()}
    except (ValueError, TypeError) as e:
        logger.error(f"❌ Invalid data format for bar chart: {e}")
        return None
    
    # Determine colors for each bar
    bar_colors = []
    if colors and len(colors) == len(data):
        # Use provided colors array
        bar_colors = colors
    elif highlighted_items:
        # Use highlighting: brand color for highlighted items, muted for others
        brand_color = "#EC4899"  # Brand color for highlights
        muted_color = "#94A3B8"  # Muted color for non-highlighted
        highlighted_set = set(highlighted_items)
        bar_colors = [brand_color if key in highlighted_set else muted_color for key in data.keys()]
    else:
        # Use single color for all bars
        bar_colors = [color] * len(data)
    
    try:
        fig = go.Figure(data=[
            go.Bar(
                x=list(data.keys()),
                y=list(data.values()),
                marker_color=bar_colors,
                text=list(data.values()),
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title=title,
            xaxis_title=x_label,
            yaxis_title=y_label,
            width=width,
            height=height,
            template='plotly_white',  # Clean, professional template
            font=dict(family="Arial", size=12),
            margin=dict(l=50, r=50, t=80, b=50)
        )
        
        # Convert to PNG base64 using kaleido engine
        img_bytes = None
        if KALEIDO_AVAILABLE:
            try:
                img_bytes = to_image(fig, format="png", width=width, height=height, engine="kaleido")
            except Exception as e:
                logger.warning(f"⚠️  Kaleido engine failed: {e}")
                img_bytes = None
        
        # Fallback: try default engine (may also require kaleido)
        if img_bytes is None:
            try:
                img_bytes = to_image(fig, format="png", width=width, height=height)
            except Exception as e:
                logger.error(f"❌ Chart image export failed: {e}")
                if not KALEIDO_AVAILABLE:
                    logger.error("   Kaleido is required for PNG export. Install with: pip install kaleido")
                return None
        
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        logger.info(f"✅ Generated bar chart: {title} ({width}x{height}px)")
        return img_b64
    
    except Exception as e:
        logger.error(f"❌ Failed to generate bar chart: {e}")
        return None


def generate_line_chart(
    data: Dict[str, List[float]],
    title: str = "Chart",
    x_label: str = "X-axis",
    y_label: str = "Y-axis",
    width: int = 800,
    height: int = 600,
    colors: Optional[List[str]] = None
) -> Optional[str]:
    """
    Generate a line chart and return as base64-encoded PNG.
    
    Args:
        data: Dictionary with {series_name: [values]} pairs
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        width: Chart width in pixels
        height: Chart height in pixels
        colors: List of colors for each line (default: Plotly colors)
    
    Returns:
        Base64-encoded PNG string, or None if Plotly is not available
    """
    if not PLOTLY_AVAILABLE:
        logger.error("❌ Plotly not available. Cannot generate chart.")
        return None
    
    # Validate data
    if not data or len(data) == 0:
        logger.error("❌ Empty data provided for line chart")
        return None
    
    # Ensure all values are numeric lists
    try:
        data = {k: [float(v) for v in (vals if isinstance(vals, list) else [vals])] for k, vals in data.items()}
    except (ValueError, TypeError) as e:
        logger.error(f"❌ Invalid data format for line chart: {e}")
        return None
    
    try:
        fig = go.Figure()
        
        default_colors = ["#7C3AED", "#EC4899", "#10B981", "#F59E0B", "#3B82F6"]
        if colors is None:
            colors = default_colors
        
        for idx, (series_name, values) in enumerate(data.items()):
            fig.add_trace(go.Scatter(
                y=values,
                mode='lines+markers',
                name=series_name,
                line=dict(color=colors[idx % len(colors)], width=2),
                marker=dict(size=6)
            ))
        
        fig.update_layout(
            title=title,
            xaxis_title=x_label,
            yaxis_title=y_label,
            width=width,
            height=height,
            template='plotly_white',
            font=dict(family="Arial", size=12),
            margin=dict(l=50, r=50, t=80, b=50),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        
        # Convert to PNG base64 using kaleido engine
        img_bytes = None
        if KALEIDO_AVAILABLE:
            try:
                img_bytes = to_image(fig, format="png", width=width, height=height, engine="kaleido")
            except Exception as e:
                logger.warning(f"⚠️  Kaleido engine failed: {e}")
                img_bytes = None
        
        # Fallback: try default engine (may also require kaleido)
        if img_bytes is None:
            try:
                img_bytes = to_image(fig, format="png", width=width, height=height)
            except Exception as e:
                logger.error(f"❌ Chart image export failed: {e}")
                if not KALEIDO_AVAILABLE:
                    logger.error("   Kaleido is required for PNG export. Install with: pip install kaleido")
                return None
        
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        logger.info(f"✅ Generated line chart: {title} ({width}x{height}px)")
        return img_b64
    
    except Exception as e:
        logger.error(f"❌ Failed to generate line chart: {e}")
        return None


def generate_pie_chart(
    data: Dict[str, float],
    title: str = "Chart",
    width: int = 600,
    height: int = 600,
    colors: Optional[List[str]] = None
) -> Optional[str]:
    """
    Generate a pie chart and return as base64-encoded PNG.
    
    Args:
        data: Dictionary with {label: value} pairs
        title: Chart title
        width: Chart width in pixels
        height: Chart height in pixels
        colors: List of colors (default: Plotly colors)
    
    Returns:
        Base64-encoded PNG string, or None if Plotly is not available
    """
    if not PLOTLY_AVAILABLE:
        logger.error("❌ Plotly not available. Cannot generate chart.")
        return None
    
    # Validate data
    if not data or len(data) == 0:
        logger.error("❌ Empty data provided for pie chart")
        return None
    
    # Ensure all values are numeric
    try:
        data = {k: float(v) for k, v in data.items()}
    except (ValueError, TypeError) as e:
        logger.error(f"❌ Invalid data format for pie chart: {e}")
        return None
    
    try:
        default_colors = px.colors.qualitative.Set3
        
        fig = go.Figure(data=[go.Pie(
            labels=list(data.keys()),
            values=list(data.values()),
            marker_colors=colors or default_colors,
            textinfo='label+percent',
            textposition='outside'
        )])
        
        fig.update_layout(
            title=title,
            width=width,
            height=height,
            template='plotly_white',
            font=dict(family="Arial", size=12),
            margin=dict(l=50, r=50, t=80, b=50)
        )
        
        # Convert to PNG base64 using kaleido engine
        img_bytes = None
        if KALEIDO_AVAILABLE:
            try:
                img_bytes = to_image(fig, format="png", width=width, height=height, engine="kaleido")
            except Exception as e:
                logger.warning(f"⚠️  Kaleido engine failed: {e}")
                img_bytes = None
        
        # Fallback: try default engine (may also require kaleido)
        if img_bytes is None:
            try:
                img_bytes = to_image(fig, format="png", width=width, height=height)
            except Exception as e:
                logger.error(f"❌ Chart image export failed: {e}")
                if not KALEIDO_AVAILABLE:
                    logger.error("   Kaleido is required for PNG export. Install with: pip install kaleido")
                return None
        
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        logger.info(f"✅ Generated pie chart: {title} ({width}x{height}px)")
        return img_b64
    
    except Exception as e:
        logger.error(f"❌ Failed to generate pie chart: {e}")
        return None


def generate_chart_from_spec(chart_spec: Dict[str, Any]) -> Optional[str]:
    """
    Generate a chart from a specification dictionary.
    
    Args:
        chart_spec: Dictionary with chart configuration:
            - type: "bar" | "line" | "pie"
            - data: Data dictionary
            - title: Chart title
            - x_label: X-axis label (optional)
            - y_label: Y-axis label (optional)
            - width: Chart width (default: 800)
            - height: Chart height (default: 600)
            - color/colors: Color(s) for chart
    
    Returns:
        Base64-encoded PNG string, or None if generation fails
    """
    if not PLOTLY_AVAILABLE:
        logger.error("❌ Plotly not available. Cannot generate chart.")
        return None
    
    chart_type = chart_spec.get("chart_type", chart_spec.get("type", "bar")).lower()
    data = chart_spec.get("data", {})
    title = chart_spec.get("title", "Chart")
    width = chart_spec.get("width", 800)
    height = chart_spec.get("height", 600)
    
    if chart_type == "bar":
        return generate_bar_chart(
            data=data,
            title=title,
            x_label=chart_spec.get("x_label", "Category"),
            y_label=chart_spec.get("y_label", "Value"),
            width=width,
            height=height,
            color=chart_spec.get("color", "#7C3AED"),
            colors=chart_spec.get("colors"),
            highlighted_items=chart_spec.get("highlighted_items")
        )
    elif chart_type == "line":
        return generate_line_chart(
            data=data,
            title=title,
            x_label=chart_spec.get("x_label", "X-axis"),
            y_label=chart_spec.get("y_label", "Y-axis"),
            width=width,
            height=height,
            colors=chart_spec.get("colors")
        )
    elif chart_type == "pie":
        return generate_pie_chart(
            data=data,
            title=title,
            width=width,
            height=height,
            colors=chart_spec.get("colors")
        )
    else:
        logger.error(f"❌ Unknown chart type: {chart_type}")
        return None

