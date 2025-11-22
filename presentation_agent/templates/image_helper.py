"""
Helper functions for generating images on-the-fly using generative models.

Uses Google Imagen API (if available) or fallback services to generate
bubble-style illustrations based on keywords.
"""

import logging
from typing import Optional
from pathlib import Path

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
    
    Args:
        keyword: Image topic/keyword (e.g., "security", "warning", "analytics")
        source: Image source ("generative", "imagen", "stability", "placeholder")
        is_logo: If True, generate smaller logo-sized image (200x200), else regular image (500x500)
        
    Returns:
        Image URL (data URL, file path, or external URL)
    """
    if not keyword or not keyword.strip():
        logger.error("❌ Empty keyword provided for image generation")
        raise ValueError("Empty keyword provided for image generation")
    
    keyword = keyword.strip()
    
    # Use generative model (Imagen or Stability AI)
    if IMAGE_GENERATION_AVAILABLE and generate_image:
        try:
            # Set output directory for caching generated images
            output_dir = Path("presentation_agent/output/generated_images")
            logger.info(f"Attempting to generate image for keyword: '{keyword}' (source: {source})")
            image_url = generate_image(keyword, source=source, output_dir=output_dir, is_logo=is_logo)
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

