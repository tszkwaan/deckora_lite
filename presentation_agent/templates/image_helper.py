"""
Helper functions for generating images on-the-fly using generative models.

Uses Google Imagen API (if available) or fallback services to generate
bubble-style illustrations based on keywords.

Supports:
- Persistent cache across pipeline runs (reuse images from previous runs)
- Different images for same keyword within same pipeline run
- Parallel generation (generate multiple images concurrently)
"""

import logging
import base64
import hashlib
import json
import asyncio
from typing import Optional, Dict, List, Set
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ aiofiles not available. Using synchronous file I/O. Install with: pip install aiofiles")

logger = logging.getLogger(__name__)

# Persistent cache file path
_CACHE_FILE = Path("presentation_agent/output/image_cache.json")

# Persistent cache: maps (keyword, source, is_logo) -> list of image_urls (base64 data URLs)
# Format: {"keyword_source_islogo": [image_url1, image_url2, ...], ...}
_persistent_cache: Dict[str, List[str]] = {}

# Current run usage tracker: tracks which cached images have been used in this run
# Format: {(keyword, source, is_logo): set of used_indices}
_current_run_used: Dict[tuple, Set[int]] = {}

# Lock for async cache writes (prevents race conditions)
_cache_write_lock = None
if AIOFILES_AVAILABLE:
    try:
        _cache_write_lock = asyncio.Lock()
    except RuntimeError:
        # No event loop available, will use sync fallback
        _cache_write_lock = None


def _batch_save_cache_async():
    """
    Batch save cache asynchronously if possible, otherwise use sync save.
    This function is called from sync context but attempts async save.
    """
    try:
        if AIOFILES_AVAILABLE:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule async save as background task (non-blocking)
                asyncio.create_task(_save_persistent_cache_async())
                logger.debug("📝 Scheduled async cache save (non-blocking)")
            else:
                # No running loop, use sync save
                _save_persistent_cache()
        else:
            # aiofiles not available, use sync save
            _save_persistent_cache()
    except RuntimeError:
        # No event loop, use sync save
        _save_persistent_cache()


def _load_persistent_cache():
    """Load persistent cache from disk."""
    global _persistent_cache
    if _CACHE_FILE.exists():
        try:
            with open(_CACHE_FILE, 'r') as f:
                _persistent_cache = json.load(f)
            logger.debug(f"✅ Loaded persistent image cache: {len(_persistent_cache)} keywords")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load persistent cache: {e}")
            _persistent_cache = {}
    else:
        _persistent_cache = {}
        logger.debug("📝 No existing persistent cache found, starting fresh")


def _save_persistent_cache():
    """Save persistent cache to disk (synchronous version for backward compatibility)."""
    global _persistent_cache
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, 'w') as f:
            json.dump(_persistent_cache, f, indent=2)
        logger.debug(f"✅ Saved persistent image cache: {len(_persistent_cache)} keywords")
    except Exception as e:
        logger.warning(f"⚠️ Failed to save persistent cache: {e}")


async def _save_persistent_cache_async():
    """Save persistent cache to disk asynchronously (non-blocking)."""
    global _persistent_cache, _cache_write_lock
    if not AIOFILES_AVAILABLE:
        # Fallback to sync if aiofiles not available
        _save_persistent_cache()
        return
    
    # Initialize lock if needed (lazy initialization)
    if _cache_write_lock is None:
        try:
            _cache_write_lock = asyncio.Lock()
        except RuntimeError:
            # No event loop, fallback to sync
            _save_persistent_cache()
            return
    
    try:
        async with _cache_write_lock:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(_CACHE_FILE, 'w') as f:
                await f.write(json.dumps(_persistent_cache, indent=2))
            logger.debug(f"✅ Saved persistent image cache (async): {len(_persistent_cache)} keywords")
    except Exception as e:
        logger.warning(f"⚠️ Failed to save persistent cache (async): {e}")
        # Fallback to sync on error
        _save_persistent_cache()


# Load persistent cache on module import
_load_persistent_cache()

# Import image generation tool
try:
    from presentation_agent.agents.tools.image_generator_tool import generate_image
    IMAGE_GENERATION_AVAILABLE = True
except (ImportError, Exception) as e:
    logger.debug(f"Image generation tool not available: {e}")
    IMAGE_GENERATION_AVAILABLE = False
    generate_image = None


def clear_image_cache():
    """
    Reset the current run usage tracker (called at start of each pipeline run).
    This allows same keyword to generate different images within the same run,
    but can reuse images from persistent cache across different runs.
    
    Synchronous version for backward compatibility.
    """
    global _current_run_used
    _current_run_used.clear()
    _load_persistent_cache()  # Load cache from disk
    logger.debug("🔄 Current run usage tracker cleared, persistent cache loaded")


async def clear_image_cache_async():
    """
    Async version of clear_image_cache.
    Reset the current run usage tracker (called at start of each pipeline run).
    """
    global _current_run_used
    _current_run_used.clear()
    # Load cache synchronously (fast operation, done once at startup)
    _load_persistent_cache()
    logger.debug("🔄 Current run usage tracker cleared, persistent cache loaded (async)")

def get_image_url(keyword: str, source: str = "generative", is_logo: bool = False) -> str:
    """
    Generate an image URL for a keyword using generative models.
    
    CACHING BEHAVIOR:
    - Same keyword in SAME pipeline run → generates DIFFERENT images (no reuse within run)
    - Same keyword in DIFFERENT pipeline runs → can reuse images from persistent cache
    
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
    
    keyword_normalized = keyword.strip().lower()
    cache_key_tuple = (keyword_normalized, source, is_logo)
    cache_key_str = f"{keyword_normalized}_{source}_{is_logo}"
    
    # Check persistent cache for unused images from previous runs
    if cache_key_str in _persistent_cache:
        cached_images = _persistent_cache[cache_key_str]
        used_indices = _current_run_used.get(cache_key_tuple, set())
        
        # Find first unused image from cache
        for idx, cached_url in enumerate(cached_images):
            if idx not in used_indices:
                # Mark as used in this run
                if cache_key_tuple not in _current_run_used:
                    _current_run_used[cache_key_tuple] = set()
                _current_run_used[cache_key_tuple].add(idx)
                logger.debug(f"✅ Reusing cached image {idx+1}/{len(cached_images)} for keyword: '{keyword}' (from previous run)")
                return cached_url
    
    # No unused cached image found - generate new one
    if IMAGE_GENERATION_AVAILABLE and generate_image:
        try:
            # Set output directory for saving generated images (for debugging)
            cache_dir = Path("presentation_agent/output/generated_images")
            logger.info(f"🔄 Generating new image for keyword: '{keyword}' (source: {source}, is_logo: {is_logo})")
            image_url = generate_image(keyword_normalized, source=source, output_dir=cache_dir, is_logo=is_logo)
            if image_url:
                # Add to persistent cache for future runs (in-memory only, batch save later)
                if cache_key_str not in _persistent_cache:
                    _persistent_cache[cache_key_str] = []
                _persistent_cache[cache_key_str].append(image_url)
                # NOTE: Don't save immediately - batch save in generate_images_parallel() for better performance
                # For single image calls, cache will be saved on next batch operation or pipeline end
                
                # Mark as used in this run (so if same keyword appears again, we generate another)
                if cache_key_tuple not in _current_run_used:
                    _current_run_used[cache_key_tuple] = set()
                _current_run_used[cache_key_tuple].add(len(_persistent_cache[cache_key_str]) - 1)
                
                logger.info(f"✅ Successfully generated and cached image for '{keyword}': {image_url[:100]}...")
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
        # Deduplication path: generate unique keywords only, using persistent cache
        results: Dict[str, str] = {}  # Maps normalized keyword to image URL
        errors: Dict[str, Exception] = {}
        
        # Check persistent cache for unused images from previous runs
        keywords_to_generate_uncached = []
        for kw in keywords_to_generate:
            cache_key_tuple = (kw.lower(), source, is_logo)
            cache_key_str = f"{kw.lower()}_{source}_{is_logo}"
            
            # Check if we have unused cached images
            if cache_key_str in _persistent_cache:
                cached_images = _persistent_cache[cache_key_str]
                used_indices = _current_run_used.get(cache_key_tuple, set())
                
                # Find first unused image
                for idx, cached_url in enumerate(cached_images):
                    if idx not in used_indices:
                        # Mark as used
                        if cache_key_tuple not in _current_run_used:
                            _current_run_used[cache_key_tuple] = set()
                        _current_run_used[cache_key_tuple].add(idx)
                        results[kw] = cached_url
                        logger.debug(f"✅ Reusing cached image {idx+1}/{len(cached_images)} for '{kw}' (from previous run)")
                        break
                else:
                    # All cached images used, need to generate new
                    keywords_to_generate_uncached.append(kw)
            else:
                # No cache for this keyword, generate new
                keywords_to_generate_uncached.append(kw)
        
        # Generate only uncached keywords in parallel
        if keywords_to_generate_uncached:
            from presentation_agent.agents.tools.image_generator_tool import generate_image
            cache_dir = Path("presentation_agent/output/generated_images")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Generate uncached keywords in parallel
                future_to_keyword = {
                    executor.submit(generate_image, kw, source, cache_dir, is_logo): kw
                    for kw in keywords_to_generate_uncached
                }
                
                # Collect results as they complete and save to persistent cache
                for future in as_completed(future_to_keyword):
                    keyword = future_to_keyword[future]
                    try:
                        image_url = future.result()
                        # Add to persistent cache
                        cache_key_str = f"{keyword.lower()}_{source}_{is_logo}"
                        if cache_key_str not in _persistent_cache:
                            _persistent_cache[cache_key_str] = []
                        _persistent_cache[cache_key_str].append(image_url)
                        
                        # Mark as used in this run
                        cache_key_tuple = (keyword.lower(), source, is_logo)
                        if cache_key_tuple not in _current_run_used:
                            _current_run_used[cache_key_tuple] = set()
                        _current_run_used[cache_key_tuple].add(len(_persistent_cache[cache_key_str]) - 1)
                        
                        results[keyword] = image_url
                        logger.debug(f"✅ Generated and cached image for '{keyword}'")
                    except Exception as e:
                        logger.error(f"❌ Failed to generate image for '{keyword}': {e}")
                        errors[keyword] = e
            
            # Batch save persistent cache after all generations complete (async, non-blocking)
            _batch_save_cache_async()
        
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
        # Same keyword in same run = different images (check persistent cache for unused, then generate new)
        results: Dict[tuple, str] = {}  # Maps (index, keyword) tuple to image URL
        errors: Dict[tuple, Exception] = {}
        
        # Check persistent cache for unused images, but each occurrence needs different image
        keywords_to_generate_uncached = []
        for idx, kw_orig in keywords_to_generate_with_index:
            cache_key_tuple = (kw_orig.lower(), source, is_logo)
            cache_key_str = f"{kw_orig.lower()}_{source}_{is_logo}"
            
            # Check if we have unused cached images from previous runs
            if cache_key_str in _persistent_cache:
                cached_images = _persistent_cache[cache_key_str]
                used_indices = _current_run_used.get(cache_key_tuple, set())
                
                # Find first unused image
                for cached_idx, cached_url in enumerate(cached_images):
                    if cached_idx not in used_indices:
                        # Mark as used
                        if cache_key_tuple not in _current_run_used:
                            _current_run_used[cache_key_tuple] = set()
                        _current_run_used[cache_key_tuple].add(cached_idx)
                        results[(idx, kw_orig)] = cached_url
                        logger.debug(f"✅ Reusing cached image {cached_idx+1}/{len(cached_images)} for '{kw_orig}' (occurrence {idx}, from previous run)")
                        break
                else:
                    # All cached images used, need to generate new
                    keywords_to_generate_uncached.append((idx, kw_orig))
            else:
                # No cache for this keyword, generate new
                keywords_to_generate_uncached.append((idx, kw_orig))
        
        # Generate only uncached keywords in parallel
        if keywords_to_generate_uncached:
            from presentation_agent.agents.tools.image_generator_tool import generate_image
            cache_dir = Path("presentation_agent/output/generated_images")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit tasks for uncached keywords
                future_to_keyword = {
                    executor.submit(generate_image, kw_orig, source, cache_dir, is_logo): (idx, kw_orig)
                    for idx, kw_orig in keywords_to_generate_uncached
                }
                
                # Collect results as they complete and save to persistent cache
                for future in as_completed(future_to_keyword):
                    keyword_tuple = future_to_keyword[future]
                    idx, kw_orig = keyword_tuple
                    try:
                        image_url = future.result()
                        # Add to persistent cache
                        cache_key_str = f"{kw_orig.lower()}_{source}_{is_logo}"
                        if cache_key_str not in _persistent_cache:
                            _persistent_cache[cache_key_str] = []
                        _persistent_cache[cache_key_str].append(image_url)
                        
                        # Mark as used in this run
                        cache_key_tuple = (kw_orig.lower(), source, is_logo)
                        if cache_key_tuple not in _current_run_used:
                            _current_run_used[cache_key_tuple] = set()
                        _current_run_used[cache_key_tuple].add(len(_persistent_cache[cache_key_str]) - 1)
                        
                        results[keyword_tuple] = image_url
                        logger.debug(f"✅ Generated and cached image for '{kw_orig}' (occurrence {idx})")
                    except Exception as e:
                        logger.error(f"❌ Failed to generate image for '{kw_orig}': {e}")
                        errors[keyword_tuple] = e
            
            # Batch save persistent cache after all generations complete (async, non-blocking)
            _batch_save_cache_async()
        
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

