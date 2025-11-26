"""
Image generation tool for creating bubble-style illustrations on-the-fly.

Uses Gemini 2.5 Flash Image (Nano Banana) for fast, efficient image generation.
Generates images in a consistent bubble-style with pastel colors.
"""

import os
import base64
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import requests
import json

logger = logging.getLogger(__name__)

# Try to load .env file if available (same way as AppInitializer)
# This ensures GOOGLE_API_KEY is loaded from .env file before use
# Note: AppInitializer also loads .env, but we do it here as a fallback
# in case this module is imported before AppInitializer runs
try:
    from dotenv import load_dotenv
    # Try to load from project root (4 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)  # Don't override if already set
        logger.debug(f"✅ Loaded .env file from {env_file}")
    else:
        # Fallback: try current directory
        load_dotenv(override=False)
        logger.debug("✅ Attempted to load .env from current directory")
except ImportError:
    # python-dotenv not installed, skip .env loading
    logger.debug("python-dotenv not installed, skipping .env loading")
except Exception as e:
    logger.debug(f"Could not load .env file: {e}")

# Try to import PIL for image resizing
PIL_AVAILABLE = False
try:
    from PIL import Image
    from io import BytesIO
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    BytesIO = None

# Try to import Google Gemini API
GEMINI_AVAILABLE = False
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    logger.debug("google-genai not available for Gemini API")

# Image generation configuration
# Maximum dimensions for different image types (not fixed, just upper limits)
MAX_IMAGE_WIDTH = 500   # Maximum width for regular images
MAX_IMAGE_HEIGHT = 500  # Maximum height for regular images
MAX_LOGO_WIDTH = 200    # Maximum width for logos/icons
MAX_LOGO_HEIGHT = 200   # Maximum height for logos/icons
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"  # Nano Banana model

# Base style prompt template
IMAGE_STYLE_PROMPT_TEMPLATE = """CRITICAL: Generate a FLAT 2D SEMANTIC LOGO ICON - NOT a photograph, NOT 3D, NOT realistic.

MANDATORY STYLE REQUIREMENTS (MUST FOLLOW):
1. FLAT 2D DESIGN ONLY:
   - ABSOLUTELY NO 3D effects, shadows, depth, gradients, or realistic rendering
   - NO photographs, NO photorealistic images, NO realistic scenes
   - Use ONLY flat geometric shapes with solid colors
   - Think like a simple icon or logo - completely flat, like a vector graphic

2. SEMANTIC/CONCEPTUAL REPRESENTATION:
   - Use visual metaphors and symbols to represent the concept
   - Think: "How would I draw this as a simple icon?"
   - Use universal symbols: magnifying glass, speech bubbles, checkmarks, shields, arrows, charts, etc.

3. SIMPLE GEOMETRIC SHAPES AND THICK OUTLINES:
   - Circles, squares, rectangles, triangles, lines, arrows, rounded shapes
   - Simple stick figures or basic shapes (NOT detailed people)
   - Repeating patterns (dots, lines, grids) for concepts like "many" or "multiple"
   - **ALL shapes MUST have a distinct, thick, dark outline (e.g., dark blue/purple or black).**
   - **Internal details should be kept to an absolute minimum, favoring large, simple shapes.**

4. SOLID FLAT COLORS:
   - NO gradients, NO shadows, NO 3D shading
   - Use solid, flat colors of any hue (purple, blue, teal, orange, pink, green, yellow, red, etc.)
   - Each element should be a single solid color.
   - **The outline color should be distinct from the fill, typically a darker version of a primary color or a neutral dark tone.**

5. ICON-LIKE APPEARANCE (APP ICON/DOODLE STYLE):
   - Simple, recognizable, scalable (like an app icon)
   - Clean and minimal design
   - Center-focused composition
   - **Emphasize a slightly rounded, friendly, and 'doodle' or 'app icon' aesthetic, similar to the "KEYWORD" and "CV" examples.**

EXAMPLES OF CORRECT STYLE (UPDATED):
- "Vast amount" → Dense grid of simple outlined stick figures (flat, no detail, thick outlines)
- "Various format" → Grid of flat colored speech bubbles with simple outlined symbols inside (flat shapes, solid colors, thick outlines)
- "Search/Keyword" → Simple **outlined** magnifying glass over **outlined** flat text bubble with "KEYWORD" text. **(Like the example provided)**
- "Security" → Simple **outlined** flat shield or lock icon (outline or solid shape, no 3D). **(More minimal than your current AI safeguard)**
- "Evaluation/Comparison" → Two **outlined** flat shapes (circles or squares) with an **outlined** arrow or equals sign between them
- "Data/Analytics" → Simple **outlined** flat bar chart or line graph (geometric shapes only)

ABSOLUTELY FORBIDDEN:
- ❌ NO realistic photographs (lakes, sunsets, flags, landscapes, people, objects)
- ❌ NO 3D rendering, shadows, depth, gradients
- ❌ NO complex illustrations or detailed artwork with many small elements
- ❌ NO photorealistic images of any kind

REQUIRED OUTPUT:
- ✅ FLAT 2D geometric shapes only
- ✅ Solid colors, no gradients
- ✅ Simple symbols and patterns
- ✅ Icon/logo style, like a vector graphic, with **distinct thick outlines**

CRITICAL BACKGROUND REQUIREMENTS:
- ✅ **MUST have a SOLID WHITE background.**
- ❌ **ABSOLUTELY NO transparent background, NO colored background, NO checkerboard pattern, NO grid pattern.**
- ✅ The icon itself should be the ONLY visible content, centered on the white background.
- ❌ ABSOLUTELY NO borders, frames, circles, squares, or decorative elements around the icon, on the white background.
- ❌ NO black borders, NO colored borders, NO outlines around the entire icon.
- ❌ NO background shapes (circles, squares, etc.) behind the icon on the white background.
- ❌ NO decorative frames or containers.
- ❌ NO checkerboard/grid patterns in the background or anywhere in the image.
- ❌ NO black backgrounds, NO dark backgrounds, NO solid color backgrounds of any kind (EXCEPT for the required solid white background).

Size: Maximum {max_width}x{max_height} pixels.

Theme/Concept: {topic}

Generate a FLAT 2D SEMANTIC LOGO ICON (NOT a photo, NOT 3D) that represents "{topic}" using ONLY flat geometric shapes, solid colors, and simple symbols, **with distinct thick outlines and a minimal, app-icon/doodle aesthetic**. The icon must have a **SOLID WHITE background** with NO borders, frames, or decorative elements.
"""

def _resize_image_if_needed(image_bytes: bytes, max_width: int, max_height: int) -> bytes:
    """
    Resize image if it exceeds maximum dimensions while maintaining aspect ratio.
    
    Args:
        image_bytes: Image data as bytes
        max_width: Maximum width
        max_height: Maximum height
        
    Returns:
        Resized image bytes (or original if no resize needed)
    """
    if not PIL_AVAILABLE:
        logger.debug("PIL not available, skipping image resize")
        return image_bytes
    
    try:
        # Open image from bytes
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        
        # Check if resize is needed
        if width <= max_width and height <= max_height:
            return image_bytes  # No resize needed
        
        # Calculate new size maintaining aspect ratio
        ratio = min(max_width / width, max_height / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        
        # Resize image
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert back to bytes
        output = BytesIO()
        img_resized.save(output, format='PNG')
        output.seek(0)
        
        logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        return output.read()
        
    except Exception as e:
        logger.warning(f"Failed to resize image: {e}, returning original")
        return image_bytes


def generate_image_with_gemini(keyword: str, output_dir: Optional[Path] = None, is_logo: bool = False) -> Optional[str]:
    """
    Generate an image using Gemini 2.5 Flash Image (Nano Banana).
    
    Args:
        keyword: Image topic/keyword
        output_dir: Optional directory to save the image
        is_logo: If True, generate smaller logo-sized image (200x200), else regular image (500x500)
        
    Returns:
        Base64-encoded image data URL or file path, or None if failed
    """
    if not GEMINI_AVAILABLE:
        logger.debug("Gemini API not available")
        return None
    
    # Get API key from environment (same way as LLM agents)
    # ADK's Gemini() model automatically reads GOOGLE_API_KEY from environment
    # We do the same for image generation
    # Always try to load .env file first (in case module was imported before AppInitializer)
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        # Try loading .env file explicitly (module-level load might have failed or been too early)
        try:
            from dotenv import load_dotenv
            project_root = Path(__file__).parent.parent.parent.parent
            env_file = project_root / ".env"
            if env_file.exists():
                # Use override=True to ensure we get the latest value
                load_dotenv(env_file, override=True)
                api_key = os.getenv("GOOGLE_API_KEY")
                if api_key:
                    logger.info(f"✅ Loaded GOOGLE_API_KEY from .env file at {env_file}")
        except Exception as e:
            logger.debug(f"Could not load .env file: {e}")
    
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set, cannot use Gemini image generation")
        logger.warning("   Make sure GOOGLE_API_KEY is set in environment or .env file")
        logger.warning("   The same key used for LLM agents should work for image generation")
        logger.warning(f"   Checked .env file at: {Path(__file__).parent.parent.parent.parent / '.env'}")
        return None
    
    logger.info(f"✅ Using GOOGLE_API_KEY for image generation (key length: {len(api_key)})")
    
    try:
        # Determine maximum dimensions based on image type
        max_width = MAX_LOGO_WIDTH if is_logo else MAX_IMAGE_WIDTH
        max_height = MAX_LOGO_HEIGHT if is_logo else MAX_IMAGE_HEIGHT
        
        # Format prompt with keyword and maximum size
        prompt = IMAGE_STYLE_PROMPT_TEMPLATE.format(
            topic=keyword,
            max_width=max_width,
            max_height=max_height
        )
        
        # Initialize Gemini client
        client = genai.Client(api_key=api_key)
        
        logger.info(f"Generating image for keyword: {keyword} using {GEMINI_IMAGE_MODEL}")
        
        # Generate image using Gemini 2.5 Flash Image
        # Note: API doesn't support max width/height directly
        # We'll resize after generation if needed
        try:
            # Use the models.generate_content method with image model
            # Note: aspect_ratio might need to be passed differently or may not be supported
            # Try without config first, then with config if needed
            try:
                response = client.models.generate_content(
                    model=GEMINI_IMAGE_MODEL,
                    contents=prompt,
                )
            except Exception as config_error:
                # If that fails, log and re-raise
                logger.error(f"API call failed: {config_error}")
                raise
            
            # Extract image data from response
            # Response structure: response.candidates[0].content.parts[0].inline_data.data
            # Note: Use model_dump() to access data as the attribute may be None but dict has the data
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    # Check for image parts in the response
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            # Use model_dump() to get the actual data (attributes may be None but dict has data)
                            part_dict = part.model_dump()
                            
                            # Check for inline_data (Gemini image API returns data in inline_data)
                            if 'inline_data' in part_dict and part_dict['inline_data']:
                                inline_data = part_dict['inline_data']
                                image_data = inline_data.get('data')
                                
                                if image_data:
                                    # Image data is already bytes from Gemini API
                                    if isinstance(image_data, bytes):
                                        image_bytes = image_data
                                    elif isinstance(image_data, str):
                                        # If it's a string, try to decode as base64
                                        image_bytes = base64.b64decode(image_data)
                                    else:
                                        logger.warning(f"Unexpected image_data type: {type(image_data)}")
                                        continue
                                    
                                    # Resize image if it exceeds max dimensions
                                    image_bytes = _resize_image_if_needed(
                                        image_bytes, 
                                        max_width=max_width, 
                                        max_height=max_height
                                    )
                                    
                                    # Save to file if output_dir provided (for caching/debugging)
                                    if output_dir:
                                        output_dir.mkdir(parents=True, exist_ok=True)
                                        safe_keyword = "".join(c if c.isalnum() or c in "-_" else "_" for c in keyword)
                                        image_path = output_dir / f"{safe_keyword}.png"
                                        image_path.write_bytes(image_bytes)
                                        logger.info(f"Saved generated image to: {image_path}")
                                    
                                    # Always return as base64 data URL (embedded in HTML)
                                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                                    return f"data:image/png;base64,{base64_data}"
            
            # Alternative: Check if response has direct image_data attribute
            if hasattr(response, 'image_data'):
                image_bytes = response.image_data
                if isinstance(image_bytes, str):
                    image_bytes = base64.b64decode(image_bytes)
                
                # Resize image if it exceeds max dimensions
                image_bytes = _resize_image_if_needed(
                    image_bytes, 
                    max_width=max_width, 
                    max_height=max_height
                )
                
                # Save to file if output_dir provided (for caching/debugging)
                if output_dir:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    safe_keyword = "".join(c if c.isalnum() or c in "-_" else "_" for c in keyword)
                    image_path = output_dir / f"{safe_keyword}.png"
                    image_path.write_bytes(image_bytes)
                    logger.info(f"Saved generated image to: {image_path}")
                
                # Always return as base64 data URL (embedded in HTML)
                base64_data = base64.b64encode(image_bytes).decode('utf-8')
                return f"data:image/png;base64,{base64_data}"
            
            # If response structure is different, log for debugging
            logger.error(f"❌ Unexpected response structure from Gemini image generation for keyword '{keyword}'")
            logger.error(f"   Response type: {type(response)}")
            logger.error(f"   Response attributes: {[a for a in dir(response) if not a.startswith('_')]}")
            if hasattr(response, 'candidates'):
                logger.error(f"   Has candidates: {bool(response.candidates)}, count: {len(response.candidates) if response.candidates else 0}")
            if hasattr(response, 'text'):
                logger.error(f"   Response text (first 500 chars): {response.text[:500] if response.text else 'None'}")
            logger.error(f"   Full response structure: {response.model_dump() if hasattr(response, 'model_dump') else 'N/A'}")
            return None
            
        except AttributeError as attr_error:
            # Try alternative API call format
            logger.debug(f"First API call format failed: {attr_error}, trying alternative...")
            try:
                # Alternative: Get model and call generate_content
                model = client.models.get(GEMINI_IMAGE_MODEL)
                response = model.generate_content(prompt)
                
                # Process response (same as above)
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data'):
                                    image_data = part.inline_data.data
                                    if isinstance(image_data, str):
                                        image_bytes = base64.b64decode(image_data)
                                    else:
                                        image_bytes = image_data
                                    
                                    # Resize image if it exceeds max dimensions
                                    image_bytes = _resize_image_if_needed(
                                        image_bytes, 
                                        max_width=max_width, 
                                        max_height=max_height
                                    )
                                    
                                    # Save to file if output_dir provided (for caching/debugging)
                                    if output_dir:
                                        output_dir.mkdir(parents=True, exist_ok=True)
                                        safe_keyword = "".join(c if c.isalnum() or c in "-_" else "_" for c in keyword)
                                        image_path = output_dir / f"{safe_keyword}.png"
                                        image_path.write_bytes(image_bytes)
                                        logger.info(f"Saved generated image to: {image_path}")
                                    
                                    # Always return as base64 data URL (embedded in HTML)
                                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                                    return f"data:image/png;base64,{base64_data}"
                                    
                                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                                    return f"data:image/png;base64,{base64_data}"
            except Exception as alt_error:
                logger.error(f"Alternative Gemini API call also failed: {alt_error}")
                raise
        
        logger.error(f"❌ Gemini image generation succeeded but no image data found in response for keyword '{keyword}'")
        logger.error(f"   Response received but could not extract image data")
        logger.error(f"   Response type: {type(response)}")
        if hasattr(response, 'candidates'):
            logger.error(f"   Candidates: {len(response.candidates) if response.candidates else 0}")
            if response.candidates:
                candidate = response.candidates[0]
                logger.error(f"   First candidate type: {type(candidate)}")
                if hasattr(candidate, 'content'):
                    logger.error(f"   Candidate has content: {bool(candidate.content)}")
                    if candidate.content and hasattr(candidate.content, 'parts'):
                        logger.error(f"   Parts count: {len(candidate.content.parts) if candidate.content.parts else 0}")
                        for i, part in enumerate(candidate.content.parts):
                            logger.error(f"   Part {i} type: {type(part)}, has inline_data: {hasattr(part, 'inline_data')}")
                            if hasattr(part, 'model_dump'):
                                part_dict = part.model_dump()
                                logger.error(f"   Part {i} dict keys: {list(part_dict.keys())}")
        if hasattr(response, 'model_dump'):
            logger.error(f"   Full response dump (first 1000 chars): {str(response.model_dump())[:1000]}")
        return None
        
    except (ValueError, TypeError, KeyError) as e:
        # Data/parameter errors - log with context
        logger.error(
            f"Gemini image generation failed with data/parameter error: {type(e).__name__}: {e}",
            exc_info=True,
            extra={
                "error_type": type(e).__name__,
                "keyword": keyword,
                "max_width": max_width,
                "max_height": max_height
            }
        )
        return None
    except (OSError, IOError) as e:
        # File I/O errors - log with context
        logger.error(
            f"Gemini image generation failed with file I/O error: {type(e).__name__}: {e}",
            exc_info=True,
            extra={
                "error_type": type(e).__name__,
                "keyword": keyword,
                "output_dir": str(output_dir) if output_dir else None
            }
        )
        return None
    except Exception as e:
        # Unexpected errors - log with full context for debugging
        logger.error(
            f"Gemini image generation failed with unexpected error: {type(e).__name__}: {e}",
            exc_info=True,
            extra={
                "error_type": type(e).__name__,
                "keyword": keyword,
                "max_width": max_width,
                "max_height": max_height,
                "output_dir": str(output_dir) if output_dir else None
            }
        )
        return None


def generate_image_with_stability_ai(keyword: str, output_dir: Optional[Path] = None, is_logo: bool = False) -> Optional[str]:
    """
    Generate an image using Stability AI API (fallback option).
    
    Args:
        keyword: Image topic/keyword
        output_dir: Optional directory to save the image
        is_logo: If True, generate smaller logo-sized image
        
    Returns:
        Base64-encoded image data URL or file path, or None if failed
    """
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        logger.debug("STABILITY_API_KEY not set, skipping Stability AI")
        return None
    
    try:
        max_width = MAX_LOGO_WIDTH if is_logo else MAX_IMAGE_WIDTH
        max_height = MAX_LOGO_HEIGHT if is_logo else MAX_IMAGE_HEIGHT
        prompt = IMAGE_STYLE_PROMPT_TEMPLATE.format(topic=keyword, max_width=max_width, max_height=max_height)
        
        # Stability AI API endpoint
        url = "https://api.stability.ai/v2beta/stable-image/generate/core"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "image/*"
        }
        
        data = {
            "prompt": prompt,
            "output_format": "png",
            "aspect_ratio": "1:1",
            "mode": "generate",
            "seed": hash(keyword) % (2**32),  # Consistent seed for same keyword
        }
        
        files = {
            "none": ""  # Stability AI requires a file field
        }
        
        response = requests.post(url, headers=headers, data=data, files=files, timeout=30)
        
        if response.status_code == 200:
            image_data = response.content
            
            # Resize image if it exceeds max dimensions
            image_data = _resize_image_if_needed(
                image_data, 
                max_width=max_width, 
                max_height=max_height
            )
            
            # Save to file if output_dir provided (for caching/debugging)
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                safe_keyword = "".join(c if c.isalnum() or c in "-_" else "_" for c in keyword)
                image_path = output_dir / f"{safe_keyword}.png"
                image_path.write_bytes(image_data)
                logger.info(f"Saved generated image to: {image_path}")
            
            # Always return as base64 data URL (embedded in HTML)
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/png;base64,{base64_data}"
        else:
            logger.warning(f"Stability AI API returned status {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to generate image with Stability AI: {e}")
        return None


def generate_image_placeholder(keyword: str, is_logo: bool = False) -> str:
    """
    Generate a placeholder image URL (fallback when no API available).
    
    Args:
        keyword: Image topic/keyword
        is_logo: If True, use smaller logo size
        
    Returns:
        Placeholder image URL (using picsum.photos for reliable placeholder service)
    """
    import hashlib
    # Use picsum.photos for reliable placeholder images
    # Use keyword hash as seed for consistent images per keyword
    keyword_hash = hashlib.md5(keyword.encode()).hexdigest()[:8]
    size = MAX_LOGO_WIDTH if is_logo else MAX_IMAGE_WIDTH
    # Picsum provides reliable placeholder images with seed for consistency
    return f"https://picsum.photos/seed/{keyword_hash}/{size}/{size}"


def generate_image(keyword: str, source: str = "auto", output_dir: Optional[Path] = None, is_logo: bool = False) -> str:
    """
    Generate an image for a keyword using the best available method.
    
    Args:
        keyword: Image topic/keyword (e.g., "security", "warning", "analytics")
        source: Image source ("auto", "imagen", "stability", "placeholder")
        output_dir: Optional directory to save generated images (for caching)
        is_logo: If True, generate smaller logo-sized image (200x200), else regular image (500x500)
        
    Returns:
        Image URL (data URL, file path, or external URL)
    """
    if not keyword or not keyword.strip():
        logger.error("❌ Empty keyword provided for image generation")
        raise ValueError("Empty keyword provided for image generation")
    
    keyword = keyword.strip().lower()
    
    # Try Gemini 2.5 Flash Image first (if available and requested)
    if source in ("auto", "imagen", "gemini", "generative"):
        logger.info(f"Attempting Gemini image generation for keyword: '{keyword}'")
        gemini_result = generate_image_with_gemini(keyword, output_dir, is_logo=is_logo)
        if gemini_result:
            logger.info(f"✅ Gemini image generation succeeded for '{keyword}': {gemini_result}")
            return gemini_result
        else:
            logger.error(f"❌ Gemini image generation FAILED for keyword '{keyword}' - returned None")
            logger.error(f"   Check logs above for detailed error information")
            logger.error(f"   This should NOT happen if GOOGLE_API_KEY is set correctly")
            # DO NOT fallback to placeholder - raise error instead
            raise RuntimeError(f"Gemini image generation failed for keyword '{keyword}'. Check logs for details.")
    
    # Try Stability AI (if available and requested)
    if source in ("auto", "stability"):
        logger.info(f"Attempting Stability AI image generation for keyword: '{keyword}'")
        stability_result = generate_image_with_stability_ai(keyword, output_dir)
        if stability_result:
            logger.info(f"✅ Stability AI image generation succeeded for '{keyword}'")
            return stability_result
        else:
            logger.error(f"❌ Stability AI image generation FAILED for keyword '{keyword}' - returned None")
    
    # NO FALLBACK - raise error instead
    logger.error(f"❌ All image generation methods failed for keyword '{keyword}'")
    logger.error(f"   Gemini: {'attempted' if source in ('auto', 'imagen', 'gemini') else 'skipped'}")
    logger.error(f"   Stability AI: {'attempted' if source in ('auto', 'stability') else 'skipped'}")
    raise RuntimeError(f"Image generation failed for keyword '{keyword}'. No fallback available. Check logs for details.")


# Tool function for agent use
def generate_image_tool(keyword: str) -> Dict[str, Any]:
    """
    Tool function for agents to generate images.
    
    Args:
        keyword: Image topic/keyword
        
    Returns:
        Dict with image_url and status
    """
    try:
        # Use output directory for caching
        from config import OUTPUT_DIR_IMAGES
        output_dir = Path(OUTPUT_DIR_IMAGES)
        image_url = generate_image(keyword, source="auto", output_dir=output_dir)
        
        return {
            "status": "success",
            "image_url": image_url,
            "keyword": keyword
        }
    except Exception as e:
        logger.error(f"❌ Image generation tool failed for keyword '{keyword}': {e}")
        import traceback
        logger.error(f"   Full traceback: {traceback.format_exc()}")
        return {
            "status": "error",
            "error": str(e),
            "image_url": None  # NO fallback - return None to indicate failure
        }

