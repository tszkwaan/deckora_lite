"""
CSS and JavaScript generation functions.
"""

from typing import Dict


def _generate_global_css(theme_colors: Dict) -> str:
    """Generate global CSS that applies to all slides."""
    primary_color = theme_colors.get("primary", "#7C3AED")
    secondary_color = theme_colors.get("secondary", "#EC4899")
    text_color = theme_colors.get("text", "#1F2937")
    
    return f"""
        .slide-content {{
            display: flex;
            flex-direction: column;
            height: 100%;
            width: 100%;
            padding: 30px 40px;
            box-sizing: border-box;
        }}
        
        .slide-content.slide-with-chart {{
            display: flex;
            flex-direction: column;
        }}
        
        .slide-content.slide-with-chart .slide-title {{
            grid-column: 1 / -1;
            width: 100%;
            margin-bottom: 30px;
        }}
        
        .slide-content-wrapper {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            align-items: center;
            flex: 1;
        }}
        
        .slide-title {{
            color: {primary_color};
            margin-bottom: 30px;
            font-weight: 700;
            line-height: 1.2;
        }}
        
        .slide-body {{
            flex: 1;
            line-height: 1.6;
        }}
        
        .main-text {{
            margin-bottom: 20px;
            font-size: 1.1em;
        }}
        
        .bullet-points {{
            list-style: none;
            padding-left: 0;
        }}
        
        .bullet-points li {{
            margin-bottom: 16px;
            padding-left: 30px;
            position: relative;
        }}
        
        .bullet-points li:before {{
            content: "•";
            position: absolute;
            left: 0;
            color: {primary_color};
            font-size: 1.5em;
            line-height: 1;
        }}
        
        .chart-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 0;
            background: white;
            border-radius: 8px;
            min-height: 0;
            overflow: hidden;
            height: 100%;
            width: 100%;
        }}
        
        .chart-image {{
            max-width: 100%;
            max-height: 100%;
            width: auto;
            height: auto;
            object-fit: contain;
            border-radius: 4px;
            display: block;
        }}
        
        .icons-container {{
            display: flex;
            gap: 16px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}
        
        .slide-icon {{
            width: 48px;
            height: 48px;
            opacity: 0.8;
        }}
        
        /* Table highlighting styles */
        .data-table .highlight-row {{
            background-color: {secondary_color}15 !important;
            font-weight: 600;
        }}
        
        .data-table .highlight-row td {{
            color: {primary_color};
        }}
        
        .data-table .highlight-cell {{
            background-color: {secondary_color}15 !important;
            font-weight: 600;
            color: {primary_color};
        }}
        
        .slide-image {{
            max-width: 100%;
            max-height: 150px;
            width: auto;
            height: auto;
            object-fit: contain;
            border-radius: 8px;
            background: transparent;
            flex-shrink: 0;
            /* Ensure transparent PNGs display properly without checkerboard */
            image-rendering: -webkit-optimize-contrast;
            image-rendering: crisp-edges;
            /* Remove any default borders */
            border: none;
            outline: none;
            box-shadow: none;
        }}
        
        @media (max-width: 1024px) {{
            .slide-content-wrapper {{
                grid-template-columns: 1fr;
            }}
            
            .chart-container {{
                margin-top: 30px;
            }}
        }}
    """


def _generate_slide_css(slide: Dict, theme_colors: Dict) -> str:
    """Generate slide-specific CSS (if needed). Most styles are in global_css."""
    # For now, return empty string - all styles are global
    # But this allows for future slide-specific styling if needed
    return ""

