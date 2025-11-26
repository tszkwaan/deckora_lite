"""
Slide layout rendering functions (cover slides, fancy content, fancy charts).
"""

import logging
import re
from typing import Dict, List, Optional
from .utils import highlight_numbers_in_text, markdown_to_html

logger = logging.getLogger(__name__)


def render_cover_slide_html(
    title: str,
    subtitle: str = "",
    author_name: Optional[str] = None,
    author_title: Optional[str] = None,
    slide_number: int = 1,
    presentation_title: Optional[str] = None,
    theme_colors: Optional[Dict] = None
) -> str:
    """
    Render a modern cover slide with the provided template design.
    
    Args:
        title: Main title of the presentation
        subtitle: Subtitle or description
        author_name: Author name (optional)
        author_title: Author title/role (optional)
        slide_number: Current slide number (default: 1)
        presentation_title: Presentation title/branding (optional)
        theme_colors: Optional theme colors dict
        
    Returns:
        Rendered HTML string for the cover slide
    """
    # Default theme colors
    if theme_colors is None:
        theme_colors = {
            "primary": "#6366F1",  # indigo-500
            "background_light": "#F5F3FF",  # violet-50
            "background_dark": "#111827",  # gray-900
        }
    
    primary_color = theme_colors.get("primary", "#6366F1")
    background_light = theme_colors.get("background_light", "#F5F3FF")
    background_dark = theme_colors.get("background_dark", "#111827")
    
    # Extract main title and subtitle from title if needed
    # Title might be in format "Main Title: Subtitle" or just "Main Title"
    main_title = title
    if ":" in title:
        parts = title.split(":", 1)
        main_title = parts[0].strip()
        if not subtitle:
            subtitle = parts[1].strip()
    
    # Format subtitle - use provided or default
    if not subtitle:
        subtitle = "An in-depth analysis and presentation"
    
    # Extract header text (like "Q4 2024 Business Review") - try to get from subtitle or use a default
    # If subtitle contains date/event info, use it as header
    header_text = ""
    if subtitle and ("|" in subtitle or "presented by" in subtitle.lower()):
        # Subtitle might be "Presented by [Name] | [Event/Date]"
        # Extract the event/date part for header
        if "|" in subtitle:
            parts = subtitle.split("|")
            if len(parts) > 1:
                header_text = parts[1].strip()
                subtitle = parts[0].replace("Presented by", "").strip()
    
    # If no header extracted, try to create one from config or use subtitle first part
    if not header_text:
        # Try to extract from subtitle or use a generic header
        if subtitle and len(subtitle) < 50:
            header_text = subtitle.upper()
        else:
            header_text = "PRESENTATION"
    
    # Author info
    author_html = ""
    if author_name:
        author_title_text = author_title or ""
        author_html = f"""
            <div class="pt-4">
                <p class="font-semibold text-gray-800 dark:text-gray-100">{author_name}</p>
                {f'<p class="text-sm text-gray-500 dark:text-gray-400">{author_title_text}</p>' if author_title_text else ''}
            </div>
        """
    
    # Presentation title/branding (use presentation_title or extract from title)
    branding_text = presentation_title or main_title.split()[0] if main_title else "Deckora"
    
    # Split title into parts for highlighting (e.g., "The Future of FirmWise" -> "The Future of <span>FirmWise</span>")
    # Try to find a significant word to highlight (usually the last word or a key term)
    title_parts = main_title.split()
    if len(title_parts) > 2:
        # Highlight last word or significant word
        highlighted_word = title_parts[-1]
        title_with_highlight = " ".join(title_parts[:-1]) + f' <span class="text-primary">{highlighted_word}</span>'
    elif len(title_parts) == 2:
        # Highlight second word
        title_with_highlight = f'{title_parts[0]} <span class="text-primary">{title_parts[1]}</span>'
    else:
        title_with_highlight = main_title
    
    # Generate HTML using the provided template structure with explicit styling
    html = f"""
<div class="cover-slide-wrapper">
    <div aria-hidden="true" class="background-shape">
        <div class="shape-1"></div>
        <div class="shape-2"></div>
    </div>
    <main class="cover-slide-main">
        <div class="cover-slide-grid">
            <div class="cover-slide-left">
                <div class="cover-slide-header">
                    {f'<span class="cover-slide-header-text">{header_text}</span>' if header_text else ''}
                    <h1 class="cover-slide-title">
                        {title_with_highlight}
                    </h1>
                </div>
                <p class="cover-slide-subtitle">
                    {subtitle}
                </p>
                {author_html}
            </div>
            <div class="cover-slide-right">
                <div class="cover-slide-icon-circle">
                    <div class="cover-slide-icon-circle-outer"></div>
                    <div class="cover-slide-icon-circle-inner"></div>
                </div>
            </div>
        </div>
        <div class="cover-slide-top-right">
            <span>{branding_text}</span>
            <span class="cover-slide-divider"></span>
            <span>{str(slide_number).zfill(2)}</span>
        </div>
    </main>
</div>
"""
    
    # Add comprehensive CSS for the cover slide with explicit styling
    css = f"""
        .cover-slide-wrapper {{
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            background-color: {background_light};
        }}
        .cover-slide-wrapper .background-shape {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
            overflow: hidden;
        }}
        .cover-slide-wrapper .background-shape div {{
            position: absolute;
            transition: all 0.3s ease;
        }}
        .cover-slide-wrapper .shape-1 {{
            width: 65%;
            height: 100%;
            background-color: white;
            clip-path: polygon(0 0, 100% 0, 85% 100%, 0% 100%);
        }}
        .cover-slide-wrapper .shape-2 {{
            width: 60%;
            height: 80%;
            bottom: 0;
            right: 0;
            background-color: {primary_color}1A;
            clip-path: polygon(25% 0, 100% 0, 100% 100%, 0% 100%);
        }}
        .cover-slide-main {{
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 1280px;
            margin: 0 auto;
            padding: 32px 48px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .cover-slide-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 64px;
            align-items: center;
            flex: 1;
        }}
        .cover-slide-left {{
            display: flex;
            flex-direction: column;
            gap: 32px;
        }}
        .cover-slide-header {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .cover-slide-header-text {{
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #6B7280;
        }}
        .cover-slide-title {{
            font-size: 48px;
            line-height: 1.1;
            font-weight: 700;
            color: #111827;
            margin: 0;
        }}
        .cover-slide-title .text-primary {{
            color: {primary_color};
        }}
        .cover-slide-subtitle {{
            font-size: 18px;
            line-height: 1.6;
            color: #4B5563;
            margin: 0;
        }}
        .cover-slide-right {{
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .cover-slide-icon-circle {{
            position: relative;
            width: 288px;
            height: 288px;
        }}
        .cover-slide-icon-circle-outer {{
            position: absolute;
            inset: 0;
            background-color: {primary_color};
            border-radius: 50%;
            opacity: 0.1;
            transform: scale(1.1);
        }}
        .cover-slide-icon-circle-inner {{
            position: absolute;
            inset: 16px;
            background-color: {primary_color};
            border-radius: 50%;
            opacity: 0.2;
        }}
        .cover-slide-top-right {{
            position: absolute;
            top: 32px;
            right: 32px;
            display: flex;
            align-items: center;
            gap: 16px;
            font-size: 14px;
            color: #6B7280;
        }}
        .cover-slide-divider {{
            width: 1px;
            height: 16px;
            background-color: #D1D5DB;
        }}
        @media (max-width: 768px) {{
            .cover-slide-grid {{
                grid-template-columns: 1fr;
            }}
            .cover-slide-right {{
                display: none;
            }}
            .cover-slide-title {{
                font-size: 36px;
            }}
        }}
    """
    
    return f'<style>{css}</style>{html}'


def render_fancy_content_text_html(
    title: str,
    bullet_points: List[str],
    icon_keyword: Optional[str] = None,
    icon_name: str = "syringe",
    theme_colors: Optional[Dict] = None,
    image_cache: Optional[Dict] = None
) -> str:
    """
    Render a fancy content-text slide with dot grid background, two-column layout,
    Material Symbols icons for bullets, and decorative circular icon on the right.
    
    Args:
        title: Slide title
        bullet_points: List of bullet point strings
        icon_keyword: Optional keyword for generating an icon image
        icon_name: Material Symbol name (default: "syringe")
        theme_colors: Optional theme colors dict
        image_cache: Optional pre-generated image cache
        
    Returns:
        Rendered HTML string
    """
    # Default theme colors
    if theme_colors is None:
        theme_colors = {
            "primary": "#6D28D9",
            "background": "#F8FAFC",  # slate-50
            "text": "#1F2937"
        }
    
    primary_color = theme_colors.get("primary", "#6D28D9")
    # Use light grey background for fancy template (slate-50)
    background_color = "#F8FAFC"  # Always use slate-50 for fancy template, regardless of theme
    
    # Generate bullet points HTML with Material Symbols icons and number highlighting
    bullets_html = ""
    for point in bullet_points:
        # First apply markdown conversion (bold/italic), then highlight numbers
        processed_text = markdown_to_html(point)
        processed_text = highlight_numbers_in_text(processed_text, primary_color)
        
        bullets_html += f"""
            <li class="fancy-bullet-item">
                <span class="material-symbols-outlined fancy-bullet-icon">keyboard_double_arrow_right</span>
                <p class="fancy-bullet-text">{processed_text}</p>
            </li>
        """
    
    # Generate decorative icon on the right
    # If icon_keyword is provided, try to get an image, otherwise use Material Symbol
    icon_html = ""
    if icon_keyword and image_cache:
        # Try to get image from cache
        keyword_lower = icon_keyword.lower().strip()
        if keyword_lower in image_cache:
            image_urls = image_cache[keyword_lower]
            if image_urls:
                icon_html = f'<img src="{image_urls[0]}" class="fancy-icon-image" alt="{icon_keyword}" />'
    
    # If no image, use Material Symbol
    if not icon_html:
        icon_html = f'<span class="material-symbols-outlined fancy-icon-symbol">{icon_name}</span>'
    
    # Generate HTML
    html = f"""
<div class="fancy-content-slide">
    <div class="fancy-content-grid">
        <div class="fancy-content-left">
            <h1 class="fancy-content-title">{title}</h1>
            <ul class="fancy-bullet-list">
                {bullets_html}
            </ul>
        </div>
        <div class="fancy-content-right">
            <div class="fancy-icon-container">
                <div class="fancy-icon-glow-outer"></div>
                <div class="fancy-icon-border-outer"></div>
                <div class="fancy-icon-border-inner"></div>
                <div class="fancy-icon-center">
                    {icon_html}
                </div>
            </div>
        </div>
    </div>
</div>
"""
    
    # Generate CSS with !important flags to override global styles
    css = f"""
        .fancy-content-slide {{
            width: 100% !important;
            height: 100% !important;
            background-color: {background_color} !important;
            background-image: radial-gradient(circle at 1px 1px, #94a3b8 1px, transparent 0) !important;
            background-size: 2rem 2rem !important;
            padding: 48px 64px !important;
            box-sizing: border-box !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
        }}
        .fancy-content-grid {{
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 48px !important;
            align-items: center !important;
            width: 100% !important;
            max-width: 1152px !important;
            margin: 0 auto !important;
        }}
        .fancy-content-left {{
            display: flex !important;
            flex-direction: column !important;
            gap: 32px !important;
        }}
        .fancy-content-title {{
            font-size: 48px !important;
            font-weight: 700 !important;
            line-height: 1.2 !important;
            color: #0F172A !important;
            margin: 0 !important;
        }}
        .fancy-bullet-list {{
            list-style: none !important;
            padding: 0 !important;
            margin: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 24px !important;
        }}
        .fancy-bullet-item {{
            display: flex !important;
            align-items: flex-start !important;
            gap: 16px !important;
        }}
        .fancy-bullet-icon {{
            font-size: 24px !important;
            color: {primary_color} !important;
            margin-top: 4px !important;
            flex-shrink: 0 !important;
        }}
        .fancy-bullet-text {{
            font-size: 18px !important;
            line-height: 1.6 !important;
            color: #475569 !important;
            margin: 0 !important;
        }}
        .fancy-number-highlight {{
            color: {primary_color} !important;
            font-size: 1.4em !important;  /* 40% larger than base text (18px → ~25px) */
            font-weight: 700 !important;
            display: inline-block !important;
            line-height: 1.2 !important;
        }}
        .fancy-content-right {{
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}
        .fancy-icon-container {{
            position: relative !important;
            width: 288px !important;
            height: 288px !important;
        }}
        .fancy-icon-glow-outer {{
            position: absolute !important;
            inset: 0 !important;
            background-color: {primary_color}1A !important;
            border-radius: 50% !important;
            filter: blur(32px) !important;
        }}
        .fancy-icon-border-outer {{
            position: absolute !important;
            inset: 0 !important;
            border: 2px solid {primary_color}80 !important;
            border-radius: 50% !important;
            animation: fancy-pulse 2s ease-in-out infinite !important;
        }}
        .fancy-icon-border-inner {{
            position: absolute !important;
            inset: 16px !important;
            border: 1px solid {primary_color}80 !important;
            border-radius: 50% !important;
        }}
        .fancy-icon-center {{
            position: absolute !important;
            inset: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            background: rgba(255, 255, 255, 0.5) !important;
            backdrop-filter: blur(12px) !important;
            border-radius: 50% !important;
            border: 1px solid rgba(226, 232, 240, 0.5) !important;
            box-shadow: 0 20px 25px -5px {primary_color}1A, 0 10px 10px -5px {primary_color}0D !important;
        }}
        .fancy-icon-symbol {{
            font-size: 128px !important;
            color: {primary_color} !important;
        }}
        .fancy-icon-image {{
            width: 200px !important;
            height: 200px !important;
            object-fit: cover !important;
            border-radius: 50% !important;
        }}
        @keyframes fancy-pulse {{
            0%, 100% {{
                opacity: 0.5;
            }}
            50% {{
                opacity: 1;
            }}
        }}
        @media (max-width: 768px) {{
            .fancy-content-grid {{
                grid-template-columns: 1fr;
            }}
            .fancy-content-right {{
                display: none;
            }}
            .fancy-content-title {{
                font-size: 36px;
            }}
        }}
    """
    
    return f'<style>{css}</style>{html}'


def render_fancy_chart_html(
    title: str,
    bullet_points: List[str],
    chart_html: str,
    theme_colors: Optional[Dict] = None
) -> str:
    """
    Render a fancy chart slide with dot grid background, two-column layout,
    Material Symbols icons for bullets, and chart image on the right.
    
    Args:
        title: Slide title
        bullet_points: List of bullet point strings
        chart_html: HTML string containing the chart (chart-container div)
        theme_colors: Optional theme colors dict
        
    Returns:
        Rendered HTML string
    """
    # Default theme colors
    if theme_colors is None:
        theme_colors = {
            "primary": "#6D28D9",
            "background": "#F8FAFC",  # slate-50
            "text": "#1F2937"
        }
    
    primary_color = theme_colors.get("primary", "#6D28D9")
    # Use dot background (transparent, so global dot background shows through)
    background_color = "transparent"
    
    # Generate bullet points HTML with Material Symbols icons and number highlighting
    bullets_html = ""
    for point in bullet_points:
        # Remove leading "-", "•", ">>", or whitespace
        point_cleaned = re.sub(r'^[\s\-•>>]+', '', point).strip()
        
        # First apply markdown conversion (bold/italic), then highlight numbers
        processed_text = markdown_to_html(point_cleaned)
        processed_text = highlight_numbers_in_text(processed_text, primary_color)
        
        bullets_html += f"""
            <li class="fancy-bullet-item">
                <span class="material-symbols-outlined fancy-bullet-icon">keyboard_double_arrow_right</span>
                <p class="fancy-bullet-text">{processed_text}</p>
            </li>
        """
    
    # Extract chart image from chart_html (it should be in a chart-container div)
    # If chart_html is just the image, use it directly; otherwise extract the img tag
    chart_image_html = chart_html
    if '<div class="chart-container">' in chart_html:
        # Extract just the img tag from the container
        img_match = re.search(r'<img[^>]+>', chart_html)
        if img_match:
            chart_image_html = img_match.group(0)
    
    # Generate HTML
    html = f"""
<div class="fancy-content-slide fancy-chart-slide">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet"/>
    <div class="fancy-content-grid">
        <div class="fancy-content-left">
            <h1 class="fancy-content-title">{title}</h1>
            <ul class="fancy-bullet-list">
                {bullets_html}
            </ul>
        </div>
        <div class="fancy-content-right fancy-chart-right">
            <div class="fancy-chart-container">
                {chart_image_html}
            </div>
        </div>
    </div>
</div>
"""
    
    # Generate CSS with !important flags to override global styles
    css = f"""
        .fancy-content-slide.fancy-chart-slide {{
            width: 100% !important;
            height: 100% !important;
            background-color: {background_color} !important;
            background-image: radial-gradient(circle at 1px 1px, #94a3b8 1px, transparent 0) !important;
            background-size: 2rem 2rem !important;
            padding: 48px 64px !important;
            box-sizing: border-box !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
        }}
        .fancy-content-grid {{
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 48px !important;
            align-items: center !important;
            width: 100% !important;
            max-width: 1152px !important;
            margin: 0 auto !important;
        }}
        .fancy-content-left {{
            display: flex !important;
            flex-direction: column !important;
            gap: 32px !important;
        }}
        .fancy-content-title {{
            font-size: 48px !important;
            font-weight: 700 !important;
            line-height: 1.2 !important;
            color: #0F172A !important;
            margin: 0 !important;
        }}
        .fancy-bullet-list {{
            list-style: none !important;
            padding: 0 !important;
            margin: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 24px !important;
        }}
        .fancy-bullet-item {{
            display: flex !important;
            align-items: flex-start !important;
            gap: 16px !important;
        }}
        .fancy-bullet-icon {{
            font-family: 'Material Symbols Outlined' !important;
            font-size: 24px !important;
            color: {primary_color} !important;
            margin-top: 4px !important;
            flex-shrink: 0 !important;
            font-weight: normal !important;
            font-style: normal !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            display: inline-block !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
        }}
        .fancy-bullet-text {{
            font-size: 18px !important;
            line-height: 1.6 !important;
            color: #475569 !important;
            margin: 0 !important;
        }}
        .fancy-number-highlight {{
            color: {primary_color} !important;
            font-size: 1.4em !important;
            font-weight: 700 !important;
            display: inline-block !important;
            line-height: 1.2 !important;
        }}
        .fancy-content-right.fancy-chart-right {{
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}
        .fancy-chart-container {{
            width: 100% !important;
            max-width: 500px !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}
        .fancy-chart-container img {{
            max-width: 100% !important;
            max-height: 100% !important;
            width: auto !important;
            height: auto !important;
            object-fit: contain !important;
            border-radius: 8px !important;
        }}
        @media (max-width: 768px) {{
            .fancy-content-grid {{
                grid-template-columns: 1fr;
            }}
            .fancy-content-right.fancy-chart-right {{
                display: none;
            }}
            .fancy-content-title {{
                font-size: 36px;
            }}
        }}
    """
    
    return f'<style>{css}</style>{html}'

