"""
Image keyword collection and pre-generation functions.
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def _extract_keywords_from_items(items: list, all_keywords: list) -> None:
    """
    Helper function to extract image keywords from a list of items.
    
    Refactored to reduce repetitive nested loops in _collect_all_image_keywords.
    
    Args:
        items: List of dict items that may contain image_keyword or image fields
        all_keywords: List to append extracted keywords to (modified in-place)
    """
    for item in items:
        if isinstance(item, dict):
            image_keyword = item.get("image_keyword")
            if image_keyword and image_keyword.strip():
                all_keywords.append(image_keyword.strip())
            # Also check legacy 'image' field
            image = item.get("image")
            if image and isinstance(image, str) and not image.startswith('http'):
                all_keywords.append(image.strip())


def _collect_all_image_keywords(slides: list) -> list:
    """
    Collect all image keywords from all slides, including from template layouts.
    
    This function scans all slides to find:
    - image_keywords from visual_elements
    - icons_suggested from visual_elements
    - image_keyword from figures
    - image_keyword from template layouts (comparison-grid sections, icon-feature-card, etc.)
    
    NOTE: We preserve duplicates because same keyword on different slides/positions
    should get different images (allow_deduplication=False in generation).
    
    Args:
        slides: List of slide dicts
        
    Returns:
        List of image keywords (strings) to generate (may contain duplicates)
    """
    all_keywords = []
    
    for slide in slides:
        visual_elements = slide.get("visual_elements", {})
        design_spec = slide.get("design_spec", {})
        layout_type = design_spec.get("layout_type")
        
        # Collect from standard visual_elements
        image_keywords = visual_elements.get("image_keywords", [])
        if image_keywords:
            all_keywords.extend([kw for kw in image_keywords if kw and kw.strip()])
        
        icons_suggested = visual_elements.get("icons_suggested", [])
        if icons_suggested and not image_keywords:  # Only use if no explicit image_keywords
            all_keywords.extend([kw for kw in icons_suggested if kw and kw.strip()])
        
        # Collect from figures
        figures = visual_elements.get("figures", [])
        _extract_keywords_from_items(figures, all_keywords)
        
        # Collect from template layouts
        # Refactored: Use helper function to reduce repetitive nested loops
        if layout_type == "comparison-grid":
            sections = visual_elements.get("sections", [])
            _extract_keywords_from_items(sections, all_keywords)
        
        elif layout_type == "icon-row":
            icon_items = visual_elements.get("icon_items", [])
            _extract_keywords_from_items(icon_items, all_keywords)
        
        elif layout_type == "icon-sequence":
            sequence_items = visual_elements.get("sequence_items", [])
            _extract_keywords_from_items(sequence_items, all_keywords)
        
        elif layout_type == "linear-process":
            process_steps = visual_elements.get("process_steps", [])
            _extract_keywords_from_items(process_steps, all_keywords)
        
        elif layout_type == "workflow-diagram":
            workflow = visual_elements.get("workflow", {})
            if isinstance(workflow, dict):
                # Collect from inputs, processes, and outputs
                # Refactored: Use helper function to reduce nested loops
                inputs = workflow.get("inputs", [])
                _extract_keywords_from_items(inputs, all_keywords)
                processes = workflow.get("processes", [])
                _extract_keywords_from_items(processes, all_keywords)
                outputs = workflow.get("outputs", [])
                _extract_keywords_from_items(outputs, all_keywords)
        
        elif layout_type == "process-flow":
            flow_stages = visual_elements.get("flow_stages", [])
            for stage in flow_stages:
                if isinstance(stage, dict):
                    # Collect from inputs, process, and output
                    # Refactored: Use helper function to reduce nested loops
                    inputs = stage.get("inputs", [])
                    _extract_keywords_from_items(inputs, all_keywords)
                    process = stage.get("process", {})
                    if isinstance(process, dict):
                        image_keyword = process.get("image_keyword")
                        if image_keyword and image_keyword.strip():
                            all_keywords.append(image_keyword.strip())
                    output = stage.get("output", {})
                    if isinstance(output, dict):
                        image_keyword = output.get("image_keyword")
                        if image_keyword and image_keyword.strip():
                            all_keywords.append(image_keyword.strip())
    
    # Return all keywords (preserve duplicates - each occurrence needs separate image)
    # Filter out empty/invalid keywords
    valid_keywords = [kw for kw in all_keywords if kw and kw.strip()]
    return valid_keywords


def pre_generate_images(slide_deck: Dict) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    """
    Pre-generate all images needed for slides in parallel.
    
    Args:
        slide_deck: Slide deck JSON with slides array
        
    Returns:
        Tuple of (image_cache, keyword_usage_tracker):
        - image_cache: Maps keyword -> list of image URLs
        - keyword_usage_tracker: Maps keyword -> current index (for round-robin usage)
    """
    slides = slide_deck.get("slides", [])
    logger.info("🔄 Collecting all image keywords from all slides...")
    all_image_keywords = _collect_all_image_keywords(slides)
    
    image_cache = {}  # Maps keyword -> list of image_urls
    keyword_usage_tracker = {}  # Maps keyword -> current index (for round-robin usage)
    
    if all_image_keywords:
        logger.info(f"🖼️  Pre-generating {len(all_image_keywords)} images in parallel...")
        from presentation_agent.utils.image_helper import generate_images_parallel
        try:
            # Generate all images in parallel (no deduplication - each keyword occurrence gets separate image)
            image_results = generate_images_parallel(
                all_image_keywords,
                source="generative",
                is_logo=False,
                max_workers=10,  # Increased workers for batch generation
                allow_deduplication=False  # Generate separate images for duplicates
            )
            
            # Convert results to cache format: keyword -> list of URLs
            for keyword in all_image_keywords:
                keyword_lower = keyword.lower().strip()
                # Check results dict (may have duplicates, but we iterate in order)
                if keyword in image_results:
                    image_url = image_results[keyword]
                    if keyword_lower not in image_cache:
                        image_cache[keyword_lower] = []
                    image_cache[keyword_lower].append(image_url)
                elif keyword_lower in image_results:
                    image_url = image_results[keyword_lower]
                    if keyword_lower not in image_cache:
                        image_cache[keyword_lower] = []
                    image_cache[keyword_lower].append(image_url)
            
            # Initialize usage tracker (round-robin index for each keyword)
            for keyword_lower in image_cache:
                keyword_usage_tracker[keyword_lower] = 0
            
            logger.info(f"✅ Successfully pre-generated images for {len(image_cache)} unique keywords (total {len(all_image_keywords)} images)")
        except Exception as e:
            logger.error(f"❌ Failed to pre-generate images: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Continue without pre-generated images (will generate on-demand)
            image_cache = {}
            keyword_usage_tracker = {}
    else:
        logger.info("ℹ️  No images to pre-generate")
    
    return image_cache, keyword_usage_tracker

