"""
Slide HTML fragment generation functions.
"""

import logging
import json
from typing import Dict, Optional
from presentation_agent.utils.helpers import is_valid_chart_data, clean_chart_data
from presentation_agent.utils.template_helpers import (
    render_comparison_grid_html,
    render_data_table_html,
    render_flowchart_html,
    render_icon_row_html,
    render_fancy_chart_html,
    render_icon_sequence_html,
    render_linear_process_html,
    render_workflow_diagram_html,
    render_process_flow_html,
    markdown_to_html
)

logger = logging.getLogger(__name__)

def _generate_slide_html_fragment(slide: Dict, script_section: Optional[Dict], slide_index: int, theme_colors: Optional[Dict] = None, config: Optional[Dict] = None, image_cache: Optional[Dict] = None, keyword_usage_tracker: Optional[Dict] = None) -> str:
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
    # Ensure content is a dict (handle cases where it might be a string)
    if isinstance(content, str):
        try:
            import json
            content = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"⚠️  content is a string but not valid JSON, using empty dict. Value: {content[:100]}")
            content = {}
    if not isinstance(content, dict):
        logger.warning(f"⚠️  content is not a dict (got {type(content).__name__}), using empty dict")
        content = {}
    
    bullet_points = content.get("bullet_points", [])
    main_text = content.get("main_text")
    visual_elements = slide.get("visual_elements", {})
    # Ensure visual_elements is a dict (handle cases where it might be a string)
    if isinstance(visual_elements, str):
        try:
            import json
            visual_elements = json.loads(visual_elements)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"⚠️  visual_elements is a string but not valid JSON, using empty dict. Value: {visual_elements[:100]}")
            visual_elements = {}
    if not isinstance(visual_elements, dict):
        logger.warning(f"⚠️  visual_elements is not a dict (got {type(visual_elements).__name__}), using empty dict")
        visual_elements = {}
    
    design_spec = slide.get("design_spec", {})
    # Ensure design_spec is a dict
    if isinstance(design_spec, str):
        try:
            import json
            design_spec = json.loads(design_spec)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"⚠️  design_spec is a string but not valid JSON, using empty dict. Value: {design_spec[:100]}")
            design_spec = {}
    if not isinstance(design_spec, dict):
        logger.warning(f"⚠️  design_spec is not a dict (got {type(design_spec).__name__}), using empty dict")
        design_spec = {}
    
    # Default theme colors if not provided
    if theme_colors is None:
        theme_colors = {
            "primary": "#7C3AED",
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    
    # Default empty cache if not provided
    if image_cache is None:
        image_cache = {}
    
    # Generate content HTML
    content_html = ""
    if main_text:
        content_html += f'<div class="main-text">{main_text}</div>'
    if bullet_points:
        content_html += '<ul class="bullet-points">'
        for point in bullet_points:
            # Apply markdown conversion (bold/italic)
            point_html = markdown_to_html(point)
            content_html += f'<li>{point_html}</li>'
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
            from presentation_agent.tools.chart_generator_tool import generate_chart_tool
            
            # Handle both dict and list chart_specs
            if isinstance(chart_spec, list):
                # Multiple charts - generate HTML for all of them
                charts_html_list = []
                for idx, spec in enumerate(chart_spec):
                    if isinstance(spec, dict):
                        chart_type = spec.get('chart_type', 'bar')
                        data = spec.get('data', {})
                        title = spec.get('title', f'Chart {idx+1}')
                        x_label = spec.get('x_label')
                        y_label = spec.get('y_label')
                        width = spec.get('width', 700)
                        height = spec.get('height', 350)
                        color = spec.get('color')
                        colors = spec.get('colors')
                        highlighted_items = spec.get('highlighted_items')
                        
                        # Filter out null values from data
                        filtered_data = {k: v for k, v in data.items() if v is not None}
                        
                        if not filtered_data:
                            logger.warning(f"⚠️  No valid data in chart_spec[{idx}] for slide {slide_number}")
                            charts_html_list.append('<div class="chart-container"><p class="text-slate-400 italic">No chart data available</p></div>')
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
                                colors=colors,
                                highlighted_items=highlighted_items
                            )
                            
                            if result.get('status') == 'success' and result.get('chart_data'):
                                generated_chart_data = result.get('chart_data')
                                charts_html_list.append(f'<div class="chart-container"><img src="data:image/png;base64,{generated_chart_data}" alt="{title}" class="chart-image"></div>')
                                logger.info(f"✅ Generated chart {idx+1} on-the-fly for slide {slide_number}")
                            else:
                                logger.warning(f"⚠️  Failed to generate chart {idx+1} for slide {slide_number}: {result.get('error', 'Unknown error')}")
                                charts_html_list.append('<div class="chart-container"><p class="text-slate-400 italic">Chart generation failed</p></div>')
                
                # Combine all charts into one HTML string
                if charts_html_list:
                    chart_html = '<div class="charts-container" style="display: flex; flex-direction: column; gap: 20px;">' + ''.join(charts_html_list) + '</div>'
                else:
                    chart_html = '<div class="chart-container"><p class="text-slate-400 italic">No charts generated</p></div>'
            elif isinstance(chart_spec, dict):
                # Single chart
                chart_type = chart_spec.get('chart_type', 'bar')
                data = chart_spec.get('data', {})
                title = chart_spec.get('title', 'Chart')
                x_label = chart_spec.get('x_label')
                y_label = chart_spec.get('y_label')
                width = chart_spec.get('width', 800)
                height = chart_spec.get('height', 600)
                color = chart_spec.get('color')
                colors = chart_spec.get('colors')
                highlighted_items = chart_spec.get('highlighted_items')
                
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
                        colors=colors,
                        highlighted_items=highlighted_items
                    )
                    
                    if result.get('status') == 'success' and result.get('chart_data'):
                        generated_chart_data = result.get('chart_data')
                        chart_html = f'<div class="chart-container"><img src="data:image/png;base64,{generated_chart_data}" alt="{title}" class="chart-image"></div>'
                        logger.info(f"✅ Generated chart on-the-fly for slide {slide_number}")
                    else:
                        logger.warning(f"⚠️  Failed to generate chart for slide {slide_number}: {result.get('error', 'Unknown error')}")
                        chart_html = '<div class="chart-container"><p class="text-slate-400 italic">Chart generation failed</p></div>'
            else:
                logger.warning(f"⚠️  Invalid chart_spec type for slide {slide_number}: {type(chart_spec)}")
                chart_html = '<div class="chart-container"><p class="text-slate-400 italic">Invalid chart specification</p></div>'
        except Exception as e:
            logger.error(f"❌ Error generating chart for slide {slide_number}: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
    # OPTIMIZATION: Use pre-generated images from image_cache instead of generating on-the-fly
    images_html = ""
    image_keywords = visual_elements.get("image_keywords", [])  # List of keywords for images
    icons_suggested = visual_elements.get("icons_suggested", [])  # Suggested icon keywords
    figures = visual_elements.get("figures", [])  # Figure IDs or dicts with image_url
    
    # Collect all keywords and metadata (for lookup in cache)
    keywords_to_lookup = []  # List of (keyword, alt_text, priority) tuples
    image_items = []  # List of (url, alt_text) tuples
    
    # Priority 1: Use image_keywords if provided (explicit image keywords)
    if image_keywords:
        for keyword in image_keywords:
            if keyword and keyword.strip():
                keywords_to_lookup.append((keyword.strip(), keyword, 1))
    
    # Priority 2: Use icons_suggested if no image_keywords (agent suggested icons)
    elif icons_suggested:
        for keyword in icons_suggested:
            if keyword and keyword.strip():
                keywords_to_lookup.append((keyword.strip(), keyword, 2))
    
    # Priority 3: Process figures - check for image_keyword or image_url
    if figures and not keywords_to_lookup:
        for fig in figures:
            if isinstance(fig, dict):
                # Check for image_keyword first (generate image from keyword)
                image_keyword = fig.get("image_keyword")
                if image_keyword and image_keyword.strip():
                    alt_text = fig.get("caption") or fig.get("alt_text") or image_keyword
                    keywords_to_lookup.append((image_keyword.strip(), alt_text, 3))
                # Otherwise check for image_url (use directly, no generation needed)
                elif fig.get("image_url"):
                    image_url = fig.get("image_url")
                    alt_text = fig.get("caption") or fig.get("alt_text", "Image")
                    image_items.append((image_url, alt_text))
            # Skip string figure IDs (like "fig1", "table1") - they're report references, not image keywords
    
    # Fallback: If still no keywords and icons_suggested exists, use them
    if not keywords_to_lookup and not image_items and icons_suggested:
        for keyword in icons_suggested:
            if keyword and keyword.strip():
                keywords_to_lookup.append((keyword.strip(), keyword, 4))
    
    # Look up images from pre-generated cache (or generate on-demand if not in cache)
    if keywords_to_lookup:
        from presentation_agent.utils.image_helper import get_image_url
        for keyword, alt_text, priority in keywords_to_lookup:
            # Try cache first (case-insensitive lookup)
            keyword_lower = keyword.lower().strip()
            image_url = None
            
            # Check cache - image_cache maps keyword -> list of URLs
            if keyword_lower in image_cache:
                image_urls = image_cache[keyword_lower]
                if image_urls:
                    # Use round-robin: get next image from list, wrap around if needed
                    current_idx = keyword_usage_tracker.get(keyword_lower, 0)
                    image_url = image_urls[current_idx % len(image_urls)]
                    keyword_usage_tracker[keyword_lower] = (current_idx + 1) % len(image_urls)
            elif keyword in image_cache:
                # Try exact match (fallback)
                image_urls = image_cache[keyword]
                if image_urls:
                    current_idx = keyword_usage_tracker.get(keyword, 0)
                    image_url = image_urls[current_idx % len(image_urls)]
                    keyword_usage_tracker[keyword] = (current_idx + 1) % len(image_urls)
            else:
                # Not in cache - generate on-demand (shouldn't happen if pre-generation worked)
                logger.warning(f"⚠️ Image for keyword '{keyword}' not found in cache, generating on-demand")
                try:
                    image_url = get_image_url(keyword, source="generative", is_logo=False)
                except Exception as e:
                    logger.error(f"❌ Failed to generate image for keyword '{keyword}': {e}")
                    continue
            
            if image_url:
                image_items.append((image_url, alt_text))
    
    # Generate HTML from collected image items
    # Multi-image template removed - only use first image if available
    if image_items:
        # Use only the first image (for decorative purposes in content-text layout)
        first_image_url, first_alt_text = image_items[0]
        images_html = f'<div class="slide-image-single"><img src="{first_image_url}" alt="{first_alt_text}" class="slide-image"></div>'
    
    # Check if slide uses a custom template layout
    layout_type = design_spec.get("layout_type")
    
    # Apply design spec styles
    title_font_size = design_spec.get("title_font_size", 36)
    alignment = design_spec.get("alignment", {})
    title_align = alignment.get("title", "left")
    
    # Handle cover slide (first slide or explicit cover-slide layout)
    if layout_type == "cover-slide" or slide_number == 1:
        from presentation_agent.utils.template_helpers import render_cover_slide_html
        
        # Extract title and subtitle from content
        subtitle = content.get("main_text") or content.get("subtitle") or ""
        bullet_points = content.get("bullet_points", [])
        if not subtitle and bullet_points:
            subtitle = bullet_points[0]  # Use first bullet as subtitle if no main_text
        
        # Extract author info if available (from config or slide metadata)
        author_name = config.get("author_name") if isinstance(config, dict) else None
        author_title = config.get("author_title") if isinstance(config, dict) else None
        
        # Get presentation title from config or use slide title
        presentation_title = config.get("title") if isinstance(config, dict) else slide_title
        
        return render_cover_slide_html(
            title=slide_title,
            subtitle=subtitle,
            author_name=author_name,
            author_title=author_title,
            slide_number=slide_number,
            presentation_title=presentation_title,
            theme_colors=theme_colors
        )
    
    # Handle custom template layouts
    if layout_type == "comparison-grid":
        # Extract sections from content or visual_elements
        sections = visual_elements.get("sections", [])
        if not sections:
            # Try to build sections from bullet_points or other content
            sections = []
            bullet_points = content.get("bullet_points", [])
            image_keywords = visual_elements.get("image_keywords", [])
            icons_suggested = visual_elements.get("icons_suggested", [])
            
            # Use icons_suggested first, then image_keywords, then generic keywords
            icon_sources = icons_suggested + image_keywords
            if not icon_sources:
                # Generate generic keywords from title/content
                title_lower = slide_title.lower()
                if "defense" in title_lower or "strategy" in title_lower:
                    icon_sources = ["shield", "security", "protection", "lock"]
                elif "vulnerability" in title_lower or "threat" in title_lower:
                    icon_sources = ["warning", "alert", "security", "danger"]
                elif "result" in title_lower or "effectiveness" in title_lower:
                    icon_sources = ["chart", "analytics", "data", "graph"]
                else:
                    icon_sources = ["document", "info", "feature", "item"]
            
            if bullet_points:
                # Create sections from bullet points (max 4)
                for i, point in enumerate(bullet_points[:4]):
                    # Extract title (first 3-5 words) and content (rest)
                    words = point.split()
                    if len(words) > 5:
                        title_words = words[:5]
                        content_words = words[5:]
                        section_title = " ".join(title_words)
                        section_content = " ".join(content_words)
                    else:
                        section_title = f"Item {i+1}"
                        section_content = point
                    
                    # Assign image_keyword
                    image_keyword = icon_sources[i] if i < len(icon_sources) else icon_sources[i % len(icon_sources)] if icon_sources else "document"
                    
                    sections.append({
                        "title": section_title,
                        "content": section_content,
                        "image_keyword": image_keyword,
                        "highlight": False
                    })
        
        if len(sections) >= 2:
            return render_comparison_grid_html(
                title=slide_title,
                sections=sections,
                theme_colors=theme_colors,
                title_font_size=title_font_size,
                title_align=title_align,
                image_cache=image_cache
            )
    
    elif layout_type == "data-table":
        # Extract table data from visual_elements
        table_data = visual_elements.get("table_data", {})
        
        # Ensure table_data is a dict (handle cases where it might be a string or None)
        if isinstance(table_data, str):
            try:
                import json
                table_data = json.loads(table_data)
                logger.info(f"✅ Parsed table_data from JSON string for slide {slide_number}")
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"⚠️  table_data is a string but not valid JSON for slide {slide_number}, using empty dict. Value: {table_data[:100]}")
                table_data = {}
        if not isinstance(table_data, dict):
            logger.warning(f"⚠️  table_data is not a dict (got {type(table_data).__name__}) for slide {slide_number}, using empty dict. Value: {str(table_data)[:100]}")
            table_data = {}
        
        # Safely extract headers and rows
        headers = []
        rows = []
        if table_data:
            headers_raw = table_data.get("headers", [])
            rows_raw = table_data.get("rows", [])
            
            # Ensure headers is a list
            if isinstance(headers_raw, list):
                headers = headers_raw
            else:
                logger.warning(f"⚠️  headers is not a list (got {type(headers_raw).__name__}) for slide {slide_number}")
                headers = []
            
            # Ensure rows is a list
            if isinstance(rows_raw, list):
                rows = rows_raw
            else:
                logger.warning(f"⚠️  rows is not a list (got {type(rows_raw).__name__}) for slide {slide_number}")
                rows = []
        
        if headers and rows:
            # Render table
            table_html = render_data_table_html(
                headers=headers,
                rows=rows,
                theme_colors=theme_colors,
                style=table_data.get("style", "striped"),
                highlight_rows=table_data.get("highlight_rows"),
                highlight_columns=table_data.get("highlight_columns"),
                caption=table_data.get("caption")
            )
            
            # Render page layout with table
            from presentation_agent.utils.template_loader import render_page_layout
            variables = {
                "title": slide_title,
                "table_html": table_html,
                "title_font_size": title_font_size,
                "title_align": title_align,
                "additional_content_html": content_html if content_html else ""
            }
            return render_page_layout("data-table", variables, theme_colors)
        else:
            # Fallback: if table_data is missing, render as normal text content
            logger.info(f"ℹ️  layout_type is 'data-table' but no table_data available for slide {slide_number}, falling back to normal text content")
            # Continue to normal text rendering below (don't return early)
    
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
        
        # Fallback: Auto-generate icon_items from bullet_points + image_keywords/icons_suggested
        if not icon_items:
            bullet_points = content.get("bullet_points", [])
            image_keywords = visual_elements.get("image_keywords", [])
            icons_suggested = visual_elements.get("icons_suggested", [])
            
            # Use icons_suggested first, then image_keywords, then generic keywords
            icon_sources = icons_suggested + image_keywords
            if not icon_sources:
                # Generate generic keywords from title/content
                title_lower = slide_title.lower()
                if "benchmark" in title_lower or "evaluation" in title_lower:
                    icon_sources = ["checklist", "database", "analytics"]
                elif "defense" in title_lower or "strategy" in title_lower:
                    icon_sources = ["shield", "security", "protection"]
                elif "vulnerability" in title_lower or "threat" in title_lower:
                    icon_sources = ["warning", "alert", "security"]
                else:
                    icon_sources = ["document", "info", "feature"]
            
            # Create icon_items from bullet_points (max 4)
            for i, point in enumerate(bullet_points[:4]):
                if i < len(icon_sources):
                    icon_keyword = icon_sources[i]
                else:
                    icon_keyword = icon_sources[i % len(icon_sources)] if icon_sources else "document"
                
                # Extract short label from bullet point (first 5-8 words)
                words = point.split()[:8]
                label = " ".join(words)
                if len(point.split()) > 8:
                    label += "..."
                
                icon_items.append({
                    "label": label,
                    "image_keyword": icon_keyword
                })
        
        if icon_items:
            subtitle = content.get("main_text") or None
            return render_icon_row_html(
                title=slide_title,
                icon_items=icon_items,
                theme_colors=theme_colors,
                subtitle=subtitle,
                image_cache=image_cache,
            )
    
    elif layout_type == "icon-sequence":
        sequence_items = visual_elements.get("sequence_items", [])
        if sequence_items:
            goal_text = content.get("main_text") or None
            return render_icon_sequence_html(
                title=slide_title,
                sequence_items=sequence_items,
                theme_colors=theme_colors,
                goal_text=goal_text,
                image_cache=image_cache,
            )
    
    elif layout_type == "linear-process":
        process_steps = visual_elements.get("process_steps", [])
        if process_steps:
            section_header = visual_elements.get("section_header") or None
            return render_linear_process_html(
                title=slide_title,
                process_steps=process_steps,
                theme_colors=theme_colors,
                section_header=section_header,
                image_cache=image_cache,
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
                evaluation_criteria=evaluation_criteria,
                image_cache=image_cache,
            )
    
    elif layout_type == "process-flow":
        flow_stages = visual_elements.get("flow_stages", [])
        if flow_stages:
            section_header = visual_elements.get("section_header") or None
            return render_process_flow_html(
                title=slide_title,
                flow_stages=flow_stages,
                theme_colors=theme_colors,
                section_header=section_header,
                image_cache=image_cache,
            )
    
    # Fallback for content-with-chart when chart_spec is missing
    if layout_type == "content-with-chart" and not chart_html:
        # If chart is missing, fall back to content-text layout
        layout_type = "content-text"
    
    # Default layout (existing behavior)
    has_chart = chart_html != ""
    has_images = images_html != ""
    # Multi-image template removed - use slide-text-only even if images present
    layout_class = "slide-with-chart" if charts_needed else "slide-text-only"
    body_font_size = design_spec.get("body_font_size", 16)
    body_align = alignment.get("body", "left")
    
    # Check for fancy content-text template BEFORE other layouts
    # This should be checked early, but after all custom layouts
    # Use fancy template for content-text slides with bullet points (even if they have image_keywords)
    if layout_type == "content-text" and bullet_points and len(bullet_points) >= 2 and not (charts_needed and has_chart):
        try:
            from presentation_agent.utils.template_helpers import render_fancy_content_text_html
            
            # Extract icon keyword from visual_elements if available
            icon_keyword = None
            icon_name = "syringe"  # Default icon
            if visual_elements.get("image_keywords"):
                icon_keyword = visual_elements["image_keywords"][0]
            elif visual_elements.get("icons_suggested"):
                icon_keyword = visual_elements["icons_suggested"][0]
            
            # Try to infer icon name from title or content
            title_lower = slide_title.lower()
            if "injection" in title_lower or "threat" in title_lower or "problem" in title_lower:
                icon_name = "syringe"
            elif "security" in title_lower or "defense" in title_lower:
                icon_name = "shield"
            elif "analysis" in title_lower or "data" in title_lower or "finding" in title_lower:
                icon_name = "analytics"
            elif "process" in title_lower or "workflow" in title_lower:
                icon_name = "settings"
            elif "benchmark" in title_lower or "bipia" in title_lower:
                icon_name = "database"
            elif "conclusion" in title_lower:
                icon_name = "lightbulb"
            else:
                icon_name = "lightbulb"
            
            fancy_html = render_fancy_content_text_html(
                title=slide_title,
                bullet_points=bullet_points,
                icon_keyword=icon_keyword,
                icon_name=icon_name,
                theme_colors=theme_colors,
                image_cache=image_cache
            )
            if fancy_html:
                logger.info(f"✅ Using fancy template for slide {slide_number}")
                return fancy_html
            else:
                logger.warning(f"⚠️  Fancy template returned None for slide {slide_number}, falling back to standard template")
        except Exception as e:
            logger.error(f"❌ Error rendering fancy template for slide {slide_number}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # Generate HTML fragment (just the slide content, no wrapper)
    # For slides with charts, use fancy chart template (same as fancy content-text but with chart)
    if charts_needed and has_chart:
        # Use fancy chart template (same as fancy content-text but with chart instead of icon)
        if bullet_points and len(bullet_points) >= 1:
            try:
                fancy_chart_html = render_fancy_chart_html(
                    title=slide_title,
                    bullet_points=bullet_points,
                    chart_html=chart_html,
                    theme_colors=theme_colors
                )
                if fancy_chart_html:
                    logger.info(f"✅ Using fancy chart template for slide {slide_number}")
                    return fancy_chart_html
                else:
                    logger.warning(f"⚠️  Fancy chart template returned None for slide {slide_number}, falling back to standard template")
            except Exception as e:
                logger.error(f"❌ Error rendering fancy chart template for slide {slide_number}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Fallback to standard chart template
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
        return slide_html.strip()
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
        return slide_html.strip()
    else:
        # Text-only slide - use fancy template if it's a content-text layout with bullet points
        # Ensure bullet_points is defined (it should be from line 947)
        if not bullet_points:
            bullet_points = content.get("bullet_points", [])
        
        logger.debug(f"Slide {slide_number}: layout_type={layout_type}, bullet_points={bullet_points}, len={len(bullet_points) if bullet_points else 0}")
        
        if layout_type == "content-text" and bullet_points and len(bullet_points) >= 2:
            logger.info(f"🎨 Using fancy template for slide {slide_number} (content-text with {len(bullet_points)} bullet points)")
            try:
                from presentation_agent.utils.template_helpers import render_fancy_content_text_html
                
                # Extract icon keyword from visual_elements if available
                icon_keyword = None
                icon_name = "syringe"  # Default icon
                if visual_elements.get("image_keywords"):
                    icon_keyword = visual_elements["image_keywords"][0]
                elif visual_elements.get("icons_suggested"):
                    icon_keyword = visual_elements["icons_suggested"][0]
                
                # Try to infer icon name from title or content
                title_lower = slide_title.lower()
                if "injection" in title_lower or "threat" in title_lower:
                    icon_name = "syringe"
                elif "security" in title_lower or "defense" in title_lower:
                    icon_name = "shield"
                elif "analysis" in title_lower or "data" in title_lower:
                    icon_name = "analytics"
                elif "process" in title_lower or "workflow" in title_lower:
                    icon_name = "settings"
                else:
                    icon_name = "lightbulb"
                
                fancy_html = render_fancy_content_text_html(
                    title=slide_title,
                    bullet_points=bullet_points,
                    icon_keyword=icon_keyword,
                    icon_name=icon_name,
                    theme_colors=theme_colors,
                    image_cache=image_cache
                )
                if fancy_html:
                    return fancy_html
                else:
                    logger.warning(f"⚠️  Fancy template returned None for slide {slide_number}, falling back to standard template")
            except Exception as e:
                logger.error(f"❌ Error rendering fancy template for slide {slide_number}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            # Standard text-only slide
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
