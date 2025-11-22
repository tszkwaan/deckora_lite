"""
Helper functions for generating images on-the-fly using generative models.

Uses Google Imagen API (if available) or fallback services to generate
bubble-style illustrations based on keywords.

Supports:
- Cross-slide caching (cache across slides, allow duplicates on same slide)
- Parallel generation (generate multiple images concurrently)
"""

import logging
import base64
import hashlib
from typing import Optional, Dict, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Import image generation tool
try:
    from presentation_agent.agents.tools.image_generator_tool import generate_image
    IMAGE_GENERATION_AVAILABLE = True
except (ImportError, Exception) as e:
    logger.debug(f"Image generation tool not available: {e}")
    IMAGE_GENERATION_AVAILABLE = False
    generate_image = None

def get_image_url(keyword: str, source: str = "generative", is_logo: bool = False) -> str:
    """
    Generate an image URL for a keyword using generative models.
    
    NO CACHING: Every call generates a fresh image, even for the same keyword.
    
    Args:
        keyword: Image topic/keyword (e.g., "security", "warning", "analytics")
        source: Image source ("generative", "imagen", "stability", "placeholder")
        is_logo: If True, generate smaller logo-sized image (200x200), else regular image (500x500)
        
    Returns:
        Image URL (base64 data URL)
    """
    if not keyword or not keyword.strip():
        logger.error("❌ Empty keyword provided for image generation")
        raise ValueError("Empty keyword provided for image generation")
    
    keyword = keyword.strip().lower()
    
    # Generate new image (no caching - always fresh)
    if IMAGE_GENERATION_AVAILABLE and generate_image:
        try:
            # Set output directory for saving generated images (for debugging, but not used for cache)
            cache_dir = Path("presentation_agent/output/generated_images")
            logger.info(f"🔄 Generating fresh image for keyword: '{keyword}' (source: {source}, is_logo: {is_logo})")
            image_url = generate_image(keyword, source=source, output_dir=cache_dir, is_logo=is_logo)
            if image_url:
                logger.info(f"✅ Successfully generated image for '{keyword}': {image_url[:100]}...")
                return image_url
            else:
                logger.error(f"❌ Image generation returned None for keyword: '{keyword}'")
                raise RuntimeError(f"Image generation returned None for keyword '{keyword}'")
        except Exception as e:
            logger.error(f"❌ Image generation failed for keyword '{keyword}': {e}")
            import traceback
            logger.error(f"   Full traceback: {traceback.format_exc()}")
            # DO NOT fallback to placeholder - re-raise the error
            raise
    
    # If image generation is not available, raise error
    logger.error(f"❌ Image generation not available for keyword '{keyword}'")
    raise RuntimeError(f"Image generation not available. IMAGE_GENERATION_AVAILABLE={IMAGE_GENERATION_AVAILABLE}, generate_image={generate_image is not None}")


def _get_placeholder_url(keyword: str, is_logo: bool = False) -> str:
    """
    Generate a placeholder image URL (fallback when no API available).
    
    Args:
        keyword: Image topic/keyword
        is_logo: If True, use smaller logo size (200x200), else regular (500x500)
        
    Returns:
        Placeholder image URL (using picsum.photos for reliable placeholder service)
    """
    import hashlib
    # Use picsum.photos for reliable placeholder images
    # Use keyword hash as seed for consistent images per keyword
    keyword_hash = hashlib.md5(keyword.encode()).hexdigest()[:8]
    size = "200" if is_logo else "500"
    # Picsum provides reliable placeholder images with seed for consistency
    return f"https://picsum.photos/seed/{keyword_hash}/{size}/{size}"


# Legacy function names for backward compatibility
def get_storyset_image_url(keyword: str, category: Optional[str] = None) -> str:
    """Legacy function - now uses generative model."""
    return get_image_url(keyword, source="generative")


def get_unsplash_image_url(keyword: str, width: int = 400, height: int = 400) -> str:
    """Legacy function - now uses generative model."""
    return get_image_url(keyword, source="generative")


def generate_images_parallel(
    keywords: List[str], 
    source: str = "generative", 
    is_logo: bool = False, 
    max_workers: int = 5,
    allow_deduplication: bool = False
) -> Dict[str, str]:
    """
    Generate multiple images in parallel (concurrent API calls).
    
    This function:
    1. Optionally deduplicates keywords (if allow_deduplication=True)
    2. Generates all keywords concurrently using ThreadPoolExecutor
    3. Maps results back to all keywords (including duplicates if allow_deduplication=False)
    
    Args:
        keywords: List of image keywords (may contain duplicates)
        source: Image source ("generative", "imagen", "stability")
        is_logo: If True, generate smaller logo-sized images (200x200), else regular (500x500)
        max_workers: Maximum number of concurrent API calls (default: 5)
        allow_deduplication: If True, deduplicate keywords (same keyword = one API call, reuse cache).
                           If False, generate separate images for each keyword occurrence (even duplicates).
                           Default: False (generate separate images for duplicates on same slide)
        
    Returns:
        Dictionary mapping each keyword (original) to its image URL (base64 data URL)
        If allow_deduplication=True: Duplicate keywords will map to the same URL (from cache or single generation)
        If allow_deduplication=False: Each keyword occurrence gets a separate image (no deduplication)
    """
    if not keywords:
        return {}
    
    # Filter valid keywords and preserve original for mapping
    valid_keywords = [(i, kw.strip()) for i, kw in enumerate(keywords) if kw and kw.strip()]
    
    if not valid_keywords:
        logger.warning("⚠️ No valid keywords provided for parallel generation")
        return {}
    
    # Deduplicate only if allow_deduplication=True (for cross-slide caching)
    # If False, generate separate images for each occurrence (for same-slide duplicates)
    if allow_deduplication:
        # Deduplicate: same keyword = one API call, map to all occurrences
        # Use normalized keyword for generation, but map back to original
        keyword_normalized_to_originals: Dict[str, List[tuple]] = {}
        for idx, kw_orig in valid_keywords:
            kw_norm = kw_orig.lower()
            if kw_norm not in keyword_normalized_to_originals:
                keyword_normalized_to_originals[kw_norm] = []
            keyword_normalized_to_originals[kw_norm].append((idx, kw_orig))
        
        keywords_to_generate = list(keyword_normalized_to_originals.keys())
        logger.info(f"🔄 Generating {len(keywords_to_generate)} unique images in parallel (from {len(keywords)} total keywords, deduplication enabled, max_workers={max_workers})")
    else:
        # No deduplication: each keyword occurrence gets separate image
        # Track each occurrence separately using (index, keyword) tuple to handle true duplicates
        keywords_to_generate_with_index = [(idx, kw_orig) for idx, kw_orig in valid_keywords]
        keyword_index_to_original = {(idx, kw_orig): kw_orig for idx, kw_orig in valid_keywords}
        logger.info(f"🔄 Generating {len(keywords_to_generate_with_index)} images in parallel (no deduplication - each occurrence gets separate image, max_workers={max_workers})")
    
    if allow_deduplication:
        # Deduplication path: generate unique keywords only, but NO caching
        results: Dict[str, str] = {}  # Maps normalized keyword to image URL
        errors: Dict[str, Exception] = {}
        
        # Generate all unique keywords in parallel (no cache - always fresh)
        from presentation_agent.agents.tools.image_generator_tool import generate_image
        cache_dir = Path("presentation_agent/output/generated_images")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Generate all keywords in parallel (bypass cache - always fresh)
            future_to_keyword = {
                executor.submit(generate_image, kw, source, cache_dir, is_logo): kw
                for kw in keywords_to_generate
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_keyword):
                keyword = future_to_keyword[future]
                try:
                    image_url = future.result()
                    results[keyword] = image_url
                    logger.debug(f"✅ Generated image for '{keyword}'")
                except Exception as e:
                    logger.error(f"❌ Failed to generate image for '{keyword}': {e}")
                    errors[keyword] = e
        
        # Map all keywords (including duplicates) to results
        final_results: Dict[str, str] = {}
        for kw_norm, originals in keyword_normalized_to_originals.items():
            if kw_norm in results:
                # Map to all original occurrences
                for idx, kw_orig in originals:
                    final_results[kw_orig] = results[kw_norm]
            elif kw_norm in errors:
                # Skip failed keywords
                for idx, kw_orig in originals:
                    logger.warning(f"⚠️ Skipping failed keyword '{kw_orig}' in final results")
            else:
                logger.warning(f"⚠️ Keyword '{kw_norm}' not found in results (should not happen)")
    else:
        # No deduplication path: generate separate images for each occurrence
        results: Dict[tuple, str] = {}  # Maps (index, keyword) tuple to image URL
        errors: Dict[tuple, Exception] = {}
        
        # Generate all keywords in parallel (bypass cache to ensure separate images)
        from presentation_agent.agents.tools.image_generator_tool import generate_image
        cache_dir = Path("presentation_agent/output/generated_images")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks - each occurrence gets its own task
            future_to_keyword = {
                executor.submit(generate_image, kw_orig, source, cache_dir, is_logo): (idx, kw_orig)
                for idx, kw_orig in keywords_to_generate_with_index
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_keyword):
                keyword_tuple = future_to_keyword[future]
                try:
                    image_url = future.result()
                    results[keyword_tuple] = image_url
                    logger.debug(f"✅ Generated separate image for '{keyword_tuple[1]}' (occurrence {keyword_tuple[0]})")
                except Exception as e:
                    logger.error(f"❌ Failed to generate image for '{keyword_tuple[1]}': {e}")
                    errors[keyword_tuple] = e
        
        # Map results back to original keywords from input list
        # Use index to map back to the original keyword at that position
        final_results: Dict[str, str] = {}
        for idx, kw_orig in keywords_to_generate_with_index:
            keyword_tuple = (idx, kw_orig)
            if keyword_tuple in results:
                # Map to the original keyword from the input list (preserves duplicates)
                original_keyword = keywords[idx]
                final_results[original_keyword] = results[keyword_tuple]
            elif keyword_tuple in errors:
                original_keyword = keywords[idx]
                logger.warning(f"⚠️ Skipping failed keyword '{original_keyword}' in final results")
    
    logger.info(f"✅ Parallel generation complete: {len(final_results)}/{len(keywords)} images generated")
    if errors:
        logger.warning(f"⚠️ {len(errors)} images failed to generate: {list(errors.keys())}")
    
    return final_results

