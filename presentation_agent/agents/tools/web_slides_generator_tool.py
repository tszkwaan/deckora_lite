"""
Web Slides Generator Tool.
Generates an HTML webpage with interactive slides from slide deck and presentation script.
"""

import json
import base64
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from presentation_agent.agents.utils.helpers import is_valid_chart_data, clean_chart_data
from presentation_agent.templates.template_helpers import (
    render_comparison_grid_html,
    render_data_table_html,
    render_flowchart_html,
    render_timeline_html,
    render_icon_feature_card_html,
    render_icon_row_html,
    render_icon_sequence_html,
    render_linear_process_html,
    render_workflow_diagram_html,
    render_process_flow_html
)

logger = logging.getLogger(__name__)


def generate_web_slides_tool(
    slide_deck: Dict,
    presentation_script: Dict,
    config: Optional[Dict] = None,
    title: str = "Generated Presentation",
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate frontend-ready JSON format with individual slide HTML fragments for Deckora frontend.
    
    Args:
        slide_deck: Slide deck JSON with slides array
        presentation_script: Presentation script JSON
        config: Optional config dict (scenario, duration, etc.)
        title: Presentation title
        output_path: Output JSON file path (default: presentation_agent/output/slides_data.json)
        
    Returns:
        Dict with status, slides_data_path, and slides_data (for frontend)
    """
    try:
        # Default output path
        if output_path is None:
            output_dir = Path("presentation_agent/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / "slides_data.json")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract slides and script
        slides = slide_deck.get("slides", [])
        script_sections = presentation_script.get("script_sections", [])
        
        # Create script map for easy lookup
        script_map = {section.get("slide_number"): section for section in script_sections}
        
        # Generate frontend-ready JSON format (theme_colors will be computed inside)
        slides_data = _generate_frontend_slides_data(slides, script_map, title, config)
        output_path.write_text(json.dumps(slides_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        logger.info(f"✅ Frontend slides data generated: {output_path}")
        print(f"✅ Frontend slides data generated: {output_path}")
        print(f"   📊 Total slides: {len(slides_data.get('slides', []))}")
        print(f"   📦 JSON file ready for Deckora frontend integration")
        
        return {
            "status": "success",
            "slides_data_path": str(output_path.absolute()),
            "slides_data": slides_data,
            "message": "Frontend slides data generated successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating frontend slides data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to generate frontend slides data"
        }


def _generate_html(slides: list, script_map: Dict, title: str, config: Optional[Dict]) -> str:
    """Generate the complete HTML content."""
    
    # Generate slides HTML
    slides_html = []
    for idx, slide in enumerate(slides):
        slide_number = slide.get("slide_number", idx + 1)
        slide_html = _generate_slide_html(slide, script_map.get(slide_number), idx)
        slides_html.append(slide_html)
    
    # Get theme colors based on scenario
    theme_colors = _get_theme_colors(config)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        {_generate_css(theme_colors)}
    </style>
</head>
<body>
    <div class="presentation-container">
        <div class="slides-wrapper">
            {''.join(slides_html)}
        </div>
        
        <!-- Navigation -->
        <div class="navigation">
            <button class="nav-btn prev-btn" onclick="previousSlide()">← Previous</button>
            <span class="slide-counter">
                <span id="current-slide">1</span> / <span id="total-slides">{len(slides)}</span>
            </span>
            <button class="nav-btn next-btn" onclick="nextSlide()">Next →</button>
        </div>
        
        <!-- Speaker Notes Panel (toggleable) -->
        <button class="notes-toggle" onclick="toggleNotes()">📝 Notes</button>
        <div class="speaker-notes-panel" id="notes-panel">
            <div class="notes-header">
                <h3>Speaker Notes</h3>
                <button class="close-notes" onclick="toggleNotes()">×</button>
            </div>
            <div class="notes-content" id="notes-content"></div>
        </div>
    </div>
    
    <script>
        {_generate_javascript(len(slides))}
    </script>
</body>
</html>
"""
    return html


def _generate_slide_html(slide: Dict, script_section: Optional[Dict], slide_index: int) -> str:
    """Generate HTML for a single slide."""
    slide_number = slide.get("slide_number", slide_index + 1)
    slide_title = slide.get("title", "")
    content = slide.get("content", {})
    bullet_points = content.get("bullet_points", [])
    main_text = content.get("main_text")
    visual_elements = slide.get("visual_elements", {})
    design_spec = slide.get("design_spec", {})
    
    # Get speaker notes
    speaker_notes = slide.get("speaker_notes", "")
    if script_section:
        # Combine speaker notes with script content
        script_content = []
        if script_section.get("opening_line"):
            script_content.append(f"<p><strong>Opening:</strong> {script_section['opening_line']}</p>")
        for point in script_section.get("main_content", []):
            script_content.append(f"<p><strong>{point.get('point', '')}:</strong> {point.get('explanation', '')}</p>")
        if script_content:
            speaker_notes = f"<div>{speaker_notes}</div><div class='script-content'>{''.join(script_content)}</div>"
    
    # Generate content HTML
    content_html = ""
    if main_text:
        content_html += f'<div class="main-text">{main_text}</div>'
    if bullet_points:
        content_html += '<ul class="bullet-points">'
        for point in bullet_points:
            content_html += f'<li>{point}</li>'
        content_html += '</ul>'
    
    # Generate chart HTML if available
    chart_html = ""
    chart_data = visual_elements.get("chart_data")
    if is_valid_chart_data(chart_data):
        # Chart is base64 PNG - ensure it's properly formatted
        chart_data = clean_chart_data(chart_data)
        chart_html = f'<div class="chart-container"><img src="data:image/png;base64,{chart_data}" alt="Chart" class="chart-image"></div>'
    
    # Generate icons HTML if available
    icons_html = ""
    icons_fetched = visual_elements.get("icons_fetched", [])
    if icons_fetched:
        icons_html = '<div class="icons-container">'
        for icon in icons_fetched:
            icon_url = icon.get("icon_url", "")
            if icon_url:
                icons_html += f'<img src="{icon_url}" alt="{icon.get("icon_name", "icon")}" class="slide-icon">'
        icons_html += '</div>'
    
    # Determine slide layout
    charts_needed = visual_elements.get("charts_needed", False)
    has_chart = chart_html != ""
    layout_class = "slide-with-chart" if (charts_needed and has_chart) else "slide-text-only"
    
    # Apply design spec styles
    title_font_size = design_spec.get("title_font_size", 36)
    body_font_size = design_spec.get("body_font_size", 16)
    alignment = design_spec.get("alignment", {})
    title_align = alignment.get("title", "left")
    body_align = alignment.get("body", "left")
    
    slide_html = f"""
    <div class="slide {layout_class}" data-slide-number="{slide_number}" data-notes='{json.dumps(speaker_notes)}'>
        <div class="slide-content">
            <h1 class="slide-title" style="font-size: {title_font_size}pt; text-align: {title_align};">{slide_title}</h1>
            <div class="slide-body" style="font-size: {body_font_size}pt; text-align: {body_align};">
                {content_html}
            </div>
            {chart_html}
            {icons_html}
        </div>
    </div>
"""
    return slide_html


def _generate_css(theme_colors: Dict) -> str:
    """Generate CSS styles."""
    primary_color = theme_colors.get("primary", "#7C3AED")
    secondary_color = theme_colors.get("secondary", "#EC4899")
    background_color = theme_colors.get("background", "#FFFFFF")
    text_color = theme_colors.get("text", "#1F2937")
    
    return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: {text_color};
            overflow: hidden;
            height: 100vh;
        }}
        
        .presentation-container {{
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            position: relative;
        }}
        
        .slides-wrapper {{
            flex: 1;
            overflow: hidden;
            position: relative;
        }}
        
        .slide {{
            width: 100vw;
            height: 100vh;
            display: none;
            padding: 60px 80px;
            background: {background_color};
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            overflow-y: auto;
            position: absolute;
            top: 0;
            left: 0;
        }}
        
        .slide.active {{
            display: flex;
            flex-direction: column;
            z-index: 10;
        }}
        
        .slide-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            width: 100%;
            height: 100%;
            box-sizing: border-box;
        }}
        
        .slide-text-only .slide-content {{
            justify-content: center;
        }}
        
        .slide-with-chart .slide-content {{
            display: flex;
            flex-direction: column;
            gap: 20px;
            height: 100%;
            overflow: hidden;
        }}
        
        .slide-content-wrapper {{
            flex: 1;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            align-items: center;
            min-height: 0;
            overflow: hidden;
        }}
        
        .slide-title {{
            color: {primary_color};
            margin-bottom: 30px;
            font-weight: 700;
            line-height: 1.2;
            flex-shrink: 0;
        }}
        
        .slide-body {{
            flex: 1;
            line-height: 1.6;
            overflow-y: auto;
            min-height: 0;
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
        
        .navigation {{
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            gap: 20px;
            background: rgba(255, 255, 255, 0.95);
            padding: 12px 24px;
            border-radius: 50px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            z-index: 1000;
        }}
        
        .nav-btn {{
            background: {primary_color};
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }}
        
        .nav-btn:hover {{
            background: {secondary_color};
            transform: translateY(-2px);
        }}
        
        .nav-btn:disabled {{
            background: #D1D5DB;
            cursor: not-allowed;
            transform: none;
        }}
        
        .slide-counter {{
            font-weight: 600;
            color: {text_color};
            min-width: 60px;
            text-align: center;
        }}
        
        .notes-toggle {{
            position: fixed;
            top: 30px;
            right: 30px;
            background: {primary_color};
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            z-index: 1001;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}
        
        .notes-toggle:hover {{
            background: {secondary_color};
        }}
        
        .speaker-notes-panel {{
            position: fixed;
            right: -400px;
            top: 0;
            width: 400px;
            height: 100vh;
            background: white;
            box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
            transition: right 0.3s ease;
            z-index: 1002;
            display: flex;
            flex-direction: column;
        }}
        
        .speaker-notes-panel.open {{
            right: 0;
        }}
        
        .notes-header {{
            padding: 20px;
            border-bottom: 1px solid #E5E7EB;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .notes-header h3 {{
            margin: 0;
            color: {primary_color};
        }}
        
        .close-notes {{
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #6B7280;
        }}
        
        .notes-content {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            line-height: 1.6;
        }}
        
        .notes-content .script-content {{
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #E5E7EB;
        }}
        
        .notes-content .script-content p {{
            margin-bottom: 12px;
        }}
        
        /* Responsive design */
        @media (max-width: 1024px) {{
            .slide {{
                padding: 40px 40px;
            }}
            
            .slide-with-chart .slide-content {{
                grid-template-columns: 1fr;
            }}
            
            .chart-container {{
                margin-top: 30px;
            }}
        }}
        
        @media (max-width: 768px) {{
            .slide {{
                padding: 30px 20px;
            }}
            
            .navigation {{
                bottom: 20px;
                padding: 10px 16px;
            }}
            
            .nav-btn {{
                padding: 8px 16px;
                font-size: 12px;
            }}
        }}
        
        /* Keyboard navigation hint */
        .keyboard-hint {{
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            opacity: 0;
            transition: opacity 0.3s;
            z-index: 999;
        }}
        
        .keyboard-hint.show {{
            opacity: 1;
        }}
    """


def _generate_javascript(total_slides: int) -> str:
    """Generate JavaScript for slide navigation."""
    return f"""
        let currentSlideIndex = 0;
        const totalSlides = {total_slides};
        
        function showSlide(index) {{
            // Hide all slides
            const slides = document.querySelectorAll('.slide');
            slides.forEach(slide => slide.classList.remove('active'));
            
            // Show current slide
            if (slides[index]) {{
                slides[index].classList.add('active');
                currentSlideIndex = index;
                
                // Update counter
                document.getElementById('current-slide').textContent = index + 1;
                
                // Update navigation buttons
                document.querySelector('.prev-btn').disabled = (index === 0);
                document.querySelector('.next-btn').disabled = (index === totalSlides - 1);
                
                // Update speaker notes
                const notesContent = document.getElementById('notes-content');
                const currentSlide = slides[index];
                const notes = currentSlide.getAttribute('data-notes');
                if (notes) {{
                    try {{
                        notesContent.innerHTML = JSON.parse(notes);
                    }} catch (e) {{
                        notesContent.textContent = notes;
                    }}
                }} else {{
                    notesContent.textContent = 'No notes for this slide.';
                }}
            }}
        }}
        
        function nextSlide() {{
            if (currentSlideIndex < totalSlides - 1) {{
                showSlide(currentSlideIndex + 1);
            }}
        }}
        
        function previousSlide() {{
            if (currentSlideIndex > 0) {{
                showSlide(currentSlideIndex - 1);
            }}
        }}
        
        function toggleNotes() {{
            const panel = document.getElementById('notes-panel');
            panel.classList.toggle('open');
        }}
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight' || e.key === ' ') {{
                e.preventDefault();
                nextSlide();
            }} else if (e.key === 'ArrowLeft') {{
                e.preventDefault();
                previousSlide();
            }} else if (e.key === 'n' || e.key === 'N') {{
                e.preventDefault();
                toggleNotes();
            }}
        }});
        
        // Initialize
        showSlide(0);
        
        // Touch/swipe support for mobile
        let touchStartX = 0;
        let touchEndX = 0;
        
        document.addEventListener('touchstart', (e) => {{
            touchStartX = e.changedTouches[0].screenX;
        }});
        
        document.addEventListener('touchend', (e) => {{
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        }});
        
        function handleSwipe() {{
            const swipeThreshold = 50;
            if (touchEndX < touchStartX - swipeThreshold) {{
                nextSlide();
            }}
            if (touchEndX > touchStartX + swipeThreshold) {{
                previousSlide();
            }}
        }}
    """


def _generate_frontend_slides_data(slides: list, script_map: Dict, title: str, config: Optional[Dict], theme_colors: Optional[Dict] = None) -> Dict:
    """
    Generate frontend-ready JSON format with individual slide HTML fragments.
    
    Returns:
        Dict with:
        - metadata: Basic config (title, total_slides, scenario, etc.)
        - slides: Array of slide objects, each with:
          - slide_number: int
          - html: HTML fragment for this slide
          - css: CSS styles needed for this slide
          - design_spec: Design specifications
          - speaker_notes: Notes for this slide
          - script: Script content for this slide
    """
    # Get theme colors (use provided or get from config)
    if theme_colors is None:
        theme_colors = _get_theme_colors(config)
    global_css = _generate_global_css(theme_colors)
    
    slides_data = []
    for idx, slide in enumerate(slides):
        slide_number = slide.get("slide_number", idx + 1)
        script_section = script_map.get(slide_number)
        
        # Generate HTML fragment for this slide only
        slide_html = _generate_slide_html_fragment(slide, script_section, idx, theme_colors)
        
        # Extract slide-specific CSS (if any)
        slide_css = _generate_slide_css(slide, theme_colors)
        
        # Extract visual elements for chart information
        visual_elements = slide.get("visual_elements", {})
        chart_spec = visual_elements.get("chart_spec")
        charts_needed = visual_elements.get("charts_needed", False)
        
        slide_data = {
            "slide_number": slide_number,
            "html": slide_html,
            "css": slide_css,
            "design_spec": slide.get("design_spec", {}),
            "speaker_notes": slide.get("speaker_notes", ""),
            "script": script_section if script_section else None,
            "title": slide.get("title", ""),
            "has_icons": bool(visual_elements.get("icons_fetched")),
            # Chart configuration for frontend to generate charts
            "charts_needed": charts_needed,
            "chart_spec": chart_spec if chart_spec else None
        }
        slides_data.append(slide_data)
    
    return {
        "metadata": {
            "title": title,
            "total_slides": len(slides),
            "scenario": config.get("scenario", "") if config else "",
            "duration": config.get("duration", "") if config else "",
            "target_audience": config.get("target_audience", "") if config else "",
            "theme_colors": theme_colors
        },
        "global_css": global_css,
        "slides": slides_data
    }


def _generate_slide_html_fragment(slide: Dict, script_section: Optional[Dict], slide_index: int, theme_colors: Optional[Dict] = None) -> str:
    """
    Generate HTML fragment for a single slide (without wrapper HTML structure).
    This is the HTML that will be inserted into the frontend's slide container.
    
    Args:
        slide: Slide data dict
        script_section: Optional script section dict
        slide_index: Slide index (0-based)
        theme_colors: Optional theme colors dict
    """
    slide_number = slide.get("slide_number", slide_index + 1)
    slide_title = slide.get("title", "")
    content = slide.get("content", {})
    bullet_points = content.get("bullet_points", [])
    main_text = content.get("main_text")
    visual_elements = slide.get("visual_elements", {})
    design_spec = slide.get("design_spec", {})
    
    # Default theme colors if not provided
    if theme_colors is None:
        theme_colors = {
            "primary": "#7C3AED",
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    
    # Generate content HTML
    content_html = ""
    if main_text:
        content_html += f'<div class="main-text">{main_text}</div>'
    if bullet_points:
        content_html += '<ul class="bullet-points">'
        for point in bullet_points:
            content_html += f'<li>{point}</li>'
        content_html += '</ul>'
    
    # Generate chart HTML - generate chart if charts_needed but no chart_data
    chart_html = ""
    charts_needed = visual_elements.get("charts_needed", False)
    chart_data = visual_elements.get("chart_data")
    chart_spec = visual_elements.get("chart_spec")
    
    if not charts_needed:
        # No chart needed, skip
        pass
    elif is_valid_chart_data(chart_data):
        # If chart_data exists and is valid, use it
        chart_data = clean_chart_data(chart_data)
        chart_html = f'<div class="chart-container"><img src="data:image/png;base64,{chart_data}" alt="Chart" class="chart-image"></div>'
    elif chart_spec:
        # Generate chart on-the-fly from chart_spec if chart_data is missing
        try:
            from presentation_agent.agents.tools.chart_generator_tool import generate_chart_tool
            
            chart_type = chart_spec.get('chart_type', 'bar')
            data = chart_spec.get('data', {})
            title = chart_spec.get('title', 'Chart')
            x_label = chart_spec.get('x_label')
            y_label = chart_spec.get('y_label')
            width = chart_spec.get('width', 800)
            height = chart_spec.get('height', 600)
            color = chart_spec.get('color')
            colors = chart_spec.get('colors')
            
            # Filter out null values from data
            filtered_data = {k: v for k, v in data.items() if v is not None}
            
            if not filtered_data:
                logger.warning(f"⚠️  No valid data in chart_spec for slide {slide_number}")
                chart_html = '<div class="chart-container"><p class="text-slate-400 italic">No chart data available</p></div>'
            else:
                result = generate_chart_tool(
                    chart_type=chart_type,
                    data=filtered_data,
                    title=title,
                    x_label=x_label,
                    y_label=y_label,
                    width=width,
                    height=height,
                    color=color,
                    colors=colors
                )
                
                if result.get('status') == 'success' and result.get('chart_data'):
                    generated_chart_data = result.get('chart_data')
                    chart_html = f'<div class="chart-container"><img src="data:image/png;base64,{generated_chart_data}" alt="{title}" class="chart-image"></div>'
                    logger.info(f"✅ Generated chart on-the-fly for slide {slide_number}")
                else:
                    logger.warning(f"⚠️  Failed to generate chart for slide {slide_number}: {result.get('error', 'Unknown error')}")
                    chart_html = '<div class="chart-container"><p class="text-slate-400 italic">Chart generation failed</p></div>'
        except Exception as e:
            logger.error(f"❌ Error generating chart for slide {slide_number}: {e}")
            chart_html = '<div class="chart-container"><p class="text-slate-400 italic">Chart generation error</p></div>'
    else:
        # No chart_spec available
        chart_html = '<div class="chart-container"><p class="text-slate-400 italic">Chart specification not available</p></div>'
    
    # Generate icons HTML if available
    icons_html = ""
    icons_fetched = visual_elements.get("icons_fetched", [])
    if icons_fetched:
        icons_html = '<div class="icons-container">'
        for icon in icons_fetched:
            icon_url = icon.get("icon_url", "")
            if icon_url:
                icons_html += f'<img src="{icon_url}" alt="{icon.get("icon_name", "icon")}" class="slide-icon">'
        icons_html += '</div>'
    
    # Generate images HTML from image_keywords, icons_suggested, or figures
    # OPTIMIZATION: Collect all keywords first, then generate in parallel
    images_html = ""
    image_keywords = visual_elements.get("image_keywords", [])  # List of keywords for images
    icons_suggested = visual_elements.get("icons_suggested", [])  # Suggested icon keywords
    figures = visual_elements.get("figures", [])  # Figure IDs or dicts with image_url
    
    # Collect all keywords and metadata for parallel generation
    from presentation_agent.templates.image_helper import generate_images_parallel
    keywords_to_generate = []  # List of (keyword, alt_text, priority) tuples
    image_items = []  # List of (url, alt_text) tuples
    
    # Priority 1: Use image_keywords if provided (explicit image keywords)
    if image_keywords:
        for keyword in image_keywords:
            if keyword and keyword.strip():
                keywords_to_generate.append((keyword.strip(), keyword, 1))
    
    # Priority 2: Use icons_suggested if no image_keywords (agent suggested icons)
    elif icons_suggested:
        for keyword in icons_suggested:
            if keyword and keyword.strip():
                keywords_to_generate.append((keyword.strip(), keyword, 2))
    
    # Priority 3: Process figures - check for image_keyword or image_url
    if figures and not keywords_to_generate:
        for fig in figures:
            if isinstance(fig, dict):
                # Check for image_keyword first (generate image from keyword)
                image_keyword = fig.get("image_keyword")
                if image_keyword and image_keyword.strip():
                    alt_text = fig.get("caption") or fig.get("alt_text") or image_keyword
                    keywords_to_generate.append((image_keyword.strip(), alt_text, 3))
                # Otherwise check for image_url (use directly, no generation needed)
                elif fig.get("image_url"):
                    image_url = fig.get("image_url")
                    alt_text = fig.get("caption") or fig.get("alt_text", "Image")
                    image_items.append((image_url, alt_text))
            # Skip string figure IDs (like "fig1", "table1") - they're report references, not image keywords
    
    # Fallback: If still no keywords and icons_suggested exists, use them
    if not keywords_to_generate and not image_items and icons_suggested:
        for keyword in icons_suggested:
            if keyword and keyword.strip():
                keywords_to_generate.append((keyword.strip(), keyword, 4))
    
    # Generate all images in parallel (if we have keywords to generate)
    if keywords_to_generate:
        # Extract just the keywords for parallel generation
        keywords_list = [kw for kw, _, _ in keywords_to_generate]
        
        # Generate all images in parallel (concurrent API calls)
        # allow_deduplication=False: Generate separate images for duplicate keywords on same slide
        try:
            logger.info(f"🔄 Generating {len(keywords_list)} images in parallel for slide {slide_index + 1} (no deduplication - each keyword gets separate image)")
            image_results = generate_images_parallel(
                keywords_list, 
                source="generative", 
                is_logo=False, 
                max_workers=5,
                allow_deduplication=False  # Generate separate images for duplicates on same slide
            )
            
            # Map results back to keywords with their metadata
            # Iterate through keywords_list in order to preserve order and handle duplicates
            for i, (keyword, alt_text, priority) in enumerate(keywords_to_generate):
                # Use the keyword from keywords_list (same order) to look up result
                # This ensures each occurrence gets its own image, even if keyword is duplicate
                lookup_keyword = keywords_list[i] if i < len(keywords_list) else keyword
                if lookup_keyword in image_results:
                    image_url = image_results[lookup_keyword]
                    # Each keyword occurrence gets its own image (even duplicates)
                    image_items.append((image_url, alt_text))
                else:
                    logger.warning(f"⚠️ Image generation result not found for keyword '{keyword}' (index {i})")
        except Exception as e:
            logger.error(f"❌ Parallel image generation failed: {e}")
            import traceback
            logger.error(f"   Full traceback: {traceback.format_exc()}")
            # Fallback: Try sequential generation for remaining keywords
            logger.info("🔄 Falling back to sequential generation")
            from presentation_agent.templates.image_helper import get_image_url
            for keyword, alt_text, priority in keywords_to_generate:
                try:
                    # Bypass cache for same-slide duplicates by calling generate_image directly
                    from presentation_agent.agents.tools.image_generator_tool import generate_image
                    cache_dir = Path("presentation_agent/output/generated_images")
                    image_url = generate_image(keyword, source="generative", output_dir=cache_dir, is_logo=False)
                    image_items.append((image_url, alt_text))
                except Exception as e2:
                    logger.error(f"❌ Failed to generate image for keyword '{keyword}': {e2}")
                    continue
    
    # Generate HTML from collected image items
    if image_items:
        images_html = '<div class="slide-images">'
        for image_url, alt_text in image_items:
            images_html += f'<img src="{image_url}" alt="{alt_text}" class="slide-image">'
        images_html += '</div>'
    
    # Check if slide uses a custom template layout
    layout_type = design_spec.get("layout_type")
    
    # Apply design spec styles
    title_font_size = design_spec.get("title_font_size", 36)
    alignment = design_spec.get("alignment", {})
    title_align = alignment.get("title", "left")
    
    # Handle custom template layouts
    if layout_type == "comparison-grid":
        # Extract sections from content or visual_elements
        sections = visual_elements.get("sections", [])
        if not sections:
            # Try to build sections from bullet_points or other content
            sections = []
            bullet_points = content.get("bullet_points", [])
            if bullet_points:
                # Create sections from bullet points (max 4)
                for i, point in enumerate(bullet_points[:4]):
                    sections.append({
                        "title": f"Section {i+1}",
                        "content": point,
                        "highlight": False
                    })
        
        if len(sections) >= 2:
            return render_comparison_grid_html(
                title=slide_title,
                sections=sections,
                theme_colors=theme_colors,
                title_font_size=title_font_size,
                title_align=title_align
            )
    
    elif layout_type == "data-table":
        # Extract table data from visual_elements or content
        table_data = visual_elements.get("table_data", {})
        if table_data:
            headers = table_data.get("headers", [])
            rows = table_data.get("rows", [])
            if headers and rows:
                table_html = render_data_table_html(
                    headers=headers,
                    rows=rows,
                    theme_colors=theme_colors,
                    style=table_data.get("style", "default"),
                    highlight_rows=table_data.get("highlight_rows"),
                    highlight_columns=table_data.get("highlight_columns"),
                    caption=table_data.get("caption")
                )
                
                # Render page layout with table
                from presentation_agent.templates.template_loader import render_page_layout
                variables = {
                    "title": slide_title,
                    "table_html": table_html,
                    "title_font_size": title_font_size,
                    "title_align": title_align,
                    "additional_content_html": content_html if content_html else ""
                }
                return render_page_layout("data-table", variables, theme_colors)
    
    elif layout_type == "timeline":
        timeline_items = visual_elements.get("timeline_items", [])
        if timeline_items:
            return render_timeline_html(
                title=slide_title,
                timeline_items=timeline_items,
                theme_colors=theme_colors,
                title_font_size=title_font_size,
                title_align=title_align,
                orientation=visual_elements.get("timeline_orientation", "vertical")
            )
    
    elif layout_type == "flowchart":
        flowchart_steps = visual_elements.get("flowchart_steps", [])
        if not flowchart_steps:
            # Fallback: Generate flowchart steps from bullet points
            bullet_points = content.get("bullet_points", [])
            if bullet_points:
                flowchart_steps = []
                for i, point in enumerate(bullet_points, 1):
                    # Try to extract label and description from bullet point
                    # Format: "Label: Description" or just use the point as description
                    if ":" in point:
                        parts = point.split(":", 1)
                        label = parts[0].strip()
                        description = parts[1].strip()
                    else:
                        # Use first few words as label, rest as description
                        words = point.split()
                        if len(words) > 3:
                            label = " ".join(words[:2])
                            description = " ".join(words[2:])
                        else:
                            label = f"Step {i}"
                            description = point
                    flowchart_steps.append({
                        "label": label,
                        "description": description
                    })
        
        if flowchart_steps:
            flowchart_html = render_flowchart_html(
                steps=flowchart_steps,
                theme_colors=theme_colors,
                orientation=visual_elements.get("flowchart_orientation", "horizontal"),
                style=visual_elements.get("flowchart_style", "default")
            )
            # Embed flowchart in a content slide (don't show bullet points, they're in the flowchart)
            return f"""
    <div class="slide-content slide-text-only">
        <h1 class="slide-title" style="font-size: {title_font_size}pt; text-align: {title_align};">{slide_title}</h1>
        <div class="slide-body" style="font-size: 16pt; text-align: left;">
            {flowchart_html}
        </div>
    </div>
"""
    
    elif layout_type == "icon-row":
        icon_items = visual_elements.get("icon_items", [])
        if icon_items:
            subtitle = content.get("main_text") or None
            return render_icon_row_html(
                title=slide_title,
                icon_items=icon_items,
                theme_colors=theme_colors,
                subtitle=subtitle
            )
    
    elif layout_type == "icon-sequence":
        sequence_items = visual_elements.get("sequence_items", [])
        if sequence_items:
            goal_text = content.get("main_text") or None
            return render_icon_sequence_html(
                title=slide_title,
                sequence_items=sequence_items,
                theme_colors=theme_colors,
                goal_text=goal_text
            )
    
    elif layout_type == "linear-process":
        process_steps = visual_elements.get("process_steps", [])
        if process_steps:
            section_header = visual_elements.get("section_header") or None
            return render_linear_process_html(
                title=slide_title,
                process_steps=process_steps,
                theme_colors=theme_colors,
                section_header=section_header
            )
    
    elif layout_type == "workflow-diagram":
        workflow = visual_elements.get("workflow", {})
        if workflow:
            subtitle = content.get("main_text") or None
            evaluation_criteria = visual_elements.get("evaluation_criteria") or None
            return render_workflow_diagram_html(
                title=slide_title,
                workflow=workflow,
                theme_colors=theme_colors,
                subtitle=subtitle,
                evaluation_criteria=evaluation_criteria
            )
    
    elif layout_type == "process-flow":
        flow_stages = visual_elements.get("flow_stages", [])
        if flow_stages:
            section_header = visual_elements.get("section_header") or None
            return render_process_flow_html(
                title=slide_title,
                flow_stages=flow_stages,
                theme_colors=theme_colors,
                section_header=section_header
            )
    
    # Default layout (existing behavior)
    has_chart = chart_html != ""
    has_images = images_html != ""
    layout_class = "slide-with-chart" if charts_needed else ("slide-with-images" if has_images else "slide-text-only")
    body_font_size = design_spec.get("body_font_size", 16)
    body_align = alignment.get("body", "left")
    
    # Generate HTML fragment (just the slide content, no wrapper)
    # For slides with charts, wrap body and chart in a content-wrapper
    if charts_needed and has_chart:
        slide_html = f"""
    <div class="slide-content {layout_class}">
        <h1 class="slide-title" style="font-size: {title_font_size}pt; text-align: {title_align};">{slide_title}</h1>
        <div class="slide-content-wrapper">
            <div class="slide-body" style="font-size: {body_font_size}pt; text-align: {body_align};">
                {content_html}
            </div>
            {chart_html}
        </div>
        {icons_html}
    </div>
"""
    elif has_images:
        # Slide with images (but no chart) - layout similar to chart layout
        slide_html = f"""
    <div class="slide-content {layout_class}">
        <h1 class="slide-title" style="font-size: {title_font_size}pt; text-align: {title_align};">{slide_title}</h1>
        <div class="slide-content-wrapper">
            <div class="slide-body" style="font-size: {body_font_size}pt; text-align: {body_align};">
                {content_html}
            </div>
            {images_html}
        </div>
        {icons_html}
    </div>
"""
    else:
        # Text-only slide
        slide_html = f"""
    <div class="slide-content {layout_class}">
        <h1 class="slide-title" style="font-size: {title_font_size}pt; text-align: {title_align};">{slide_title}</h1>
        <div class="slide-body" style="font-size: {body_font_size}pt; text-align: {body_align};">
            {content_html}
        </div>
        {chart_html}
        {icons_html}
    </div>
"""
    return slide_html.strip()


def _generate_slide_css(slide: Dict, theme_colors: Dict) -> str:
    """Generate slide-specific CSS (if needed). Most styles are in global_css."""
    # For now, return empty string - all styles are global
    # But this allows for future slide-specific styling if needed
    return ""


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
        
        .slide-with-images .slide-content-wrapper {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            align-items: center;
            flex: 1;
        }}
        
        .slide-images {{
            display: flex;
            flex-direction: column;
            gap: 16px;
            align-items: center;
            justify-content: center;
        }}
        
        .slide-image {{
            max-width: 100%;
            max-height: 200px;
            width: auto;
            height: auto;
            object-fit: contain;
            border-radius: 8px;
            background: transparent;
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


def _get_theme_colors(config: Optional[Dict]) -> Dict[str, str]:
    """Get theme colors based on scenario."""
    if not config:
        return {
            "primary": "#7C3AED",
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    
    scenario = config.get("scenario", "").lower()
    
    if "academic" in scenario:
        return {
            "primary": "#1E40AF",  # Blue
            "secondary": "#3B82F6",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    elif "business" in scenario:
        return {
            "primary": "#059669",  # Green
            "secondary": "#10B981",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    else:
        return {
            "primary": "#7C3AED",  # Purple
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }

