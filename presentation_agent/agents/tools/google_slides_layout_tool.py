"""
Google Slides Layout Analysis Tool.
Exports slides as images and analyzes them using Google Cloud Vision API (OCR) or Gemini Vision API (prompt-based).
"""

import os
import io
import json
import base64
import re
from typing import Dict, List, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

# Optional imports - will fail gracefully if not installed
try:
    from google.cloud import vision
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    vision = None

try:
    from google.genai import Client
    GEMINI_VISION_AVAILABLE = True
except ImportError:
    GEMINI_VISION_AVAILABLE = False
    Client = None

# Check pdf2image availability at runtime, not at import time
# This allows the module to load even if pdf2image is not installed
PDF2IMAGE_AVAILABLE = None  # Will be checked at runtime
convert_from_bytes = None

# Scopes required
# Note: cloud-platform scope is needed for Vision API
SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/cloud-platform'  # Required for Vision API
]

# Path to credentials directory
CREDENTIALS_DIR = Path(__file__).parent.parent / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"


def get_credentials() -> Credentials:
    """
    Get OAuth2 credentials for Google APIs.
    If token exists, use it. Otherwise, run OAuth flow.
    Tries Secret Manager first (for Cloud Run), then falls back to local file.
    
    Returns:
        Credentials object for Google API
    """
    creds = None
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Use local files (from GitHub Secrets baked into Docker image)
    credentials_file_path = None
    
    # Create credentials directory if it doesn't exist
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    
    # Check for local credentials file
    if CREDENTIALS_FILE.exists():
        credentials_file_path = str(CREDENTIALS_FILE)
        logger.info(f"✅ Using local credentials file: {CREDENTIALS_FILE}")
    else:
        error_msg = (
            f"❌ Credentials file not found: {CREDENTIALS_FILE}\n"
            f"Please ensure GitHub Secrets GOOGLE_CREDENTIALS_JSON is set.\n"
            f"Files should be created during Docker build from GitHub Secrets."
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Use local token file
    token_file_path = None
    
    if TOKEN_FILE.exists():
        token_file_path = str(TOKEN_FILE)
        logger.info(f"✅ Using local token file: {TOKEN_FILE}")
    else:
        logger.warning(f"⚠️  Token file not found: {TOKEN_FILE}")
        logger.warning("   Please ensure GitHub Secret GOOGLE_TOKEN_JSON is set.")
    
    # Load existing token if available
    if token_file_path:
        try:
            creds = Credentials.from_authorized_user_file(token_file_path, SCOPES)
        except Exception as e:
            print(f"⚠️  Warning: Could not load token: {e}")
    
    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️  Warning: Could not refresh token: {e}")
                creds = None
        
        if not creds:
            # Run OAuth flow
            if not credentials_file_path:
                error_msg = (
                    f"❌ Credentials file not found: {CREDENTIALS_FILE}\n"
                    f"Please download credentials.json from Google Cloud Console and place it in:\n"
                    f"{CREDENTIALS_DIR}\n"
                    f"Or ensure 'google-credentials' secret exists in Secret Manager.\n"
                    f"See DEPLOYMENT_SETUP.md for setup instructions."
                )
                raise FileNotFoundError(error_msg)
            
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file_path, SCOPES
            )
            # In Cloud Run, we can't run local server, so use console flow
            if os.environ.get('PORT'):  # Running in Cloud Run
                print("⚠️  Running in Cloud Run - OAuth flow requires manual setup")
                print("   Please run OAuth flow locally and upload token.json to Secret Manager")
                raise RuntimeError(
                    "OAuth flow cannot run interactively in Cloud Run. "
                    "Please authenticate locally and upload token.json to Secret Manager."
            )
            creds = flow.run_local_server(port=0)
        
        # Save token for future use (only if not using temp file and not in Cloud Run)
        if not temp_credentials_file and not os.environ.get('PORT'):
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print("✅ Credentials saved for future use")
    
    return creds


def extract_presentation_id_from_url(url: str) -> Optional[str]:
    """
    Extract presentation ID from Google Slides shareable URL.
    
    Args:
        url: Google Slides URL (e.g., "https://docs.google.com/presentation/d/ABC123/edit")
        
    Returns:
        Presentation ID string, or None if URL format is invalid
    """
    if not url or not isinstance(url, str):
        return None
    
    # Pattern to match Google Slides URLs
    # Examples:
    # - https://docs.google.com/presentation/d/ABC123/edit
    # - https://docs.google.com/presentation/d/ABC123/view
    # - https://docs.google.com/presentation/d/ABC123
    pattern = r'/presentation/d/([a-zA-Z0-9_-]+)'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    
    return None


def verify_presentation_exists(presentation_id: str, credentials: Credentials) -> Dict:
    """
    Verify that a Google Slides presentation exists and is accessible.
    
    Args:
        presentation_id: Google Slides presentation ID
        credentials: OAuth2 credentials
        
    Returns:
        Dict with 'exists' (bool) and 'title' (str) or 'error' (str)
    """
    try:
        slides_service = build('slides', 'v1', credentials=credentials)
        presentation = slides_service.presentations().get(
            presentationId=presentation_id
        ).execute()
        return {
            'exists': True,
            'title': presentation.get('title', 'Untitled'),
            'presentation_id': presentation_id
        }
    except HttpError as error:
        error_details = error.error_details if hasattr(error, 'error_details') else []
        return {
            'exists': False,
            'error': f"Presentation {presentation_id} not found or not accessible",
            'error_details': error_details,
            'presentation_id': presentation_id
        }
    except Exception as e:
        return {
            'exists': False,
            'error': f"Error verifying presentation: {str(e)}",
            'presentation_id': presentation_id
        }


def export_slides_as_images(presentation_id: str, output_dir: str = "presentation_agent/output") -> List[bytes]:
    """
    Export Google Slides presentation as images.
    
    Steps:
    1. Export presentation as PDF using Google Drive API
    2. Save PDF to output/pdf/ directory
    3. Convert PDF pages to images (one per slide)
    
    Args:
        presentation_id: Google Slides presentation ID
        output_dir: Output directory (default: "output")
        
    Returns:
        List of image bytes (one per slide)
    """
    print("\n" + "=" * 60)
    print("📥 STEP 1: Export Google Slides to PDF")
    print("=" * 60)
    
    pdf_data = None
    
    try:
        creds = get_credentials()
        
        # First, verify the presentation exists using Slides API
        print(f"🔍 [IN PROGRESS] Verifying presentation {presentation_id} exists...")
        verification_result = verify_presentation_exists(presentation_id, creds)
        
        if not verification_result.get('exists'):
            error_msg = verification_result.get('error', 'Unknown error')
            error_details = verification_result.get('error_details', [])
            print(f"❌ [FAILED] {error_msg}")
            # Raise a ValueError instead of trying to create a fake HttpError
            raise ValueError(
                f"Presentation not found: {presentation_id}. The presentation may have been deleted or you may not have access to it. Details: {error_details}"
            )
        
        print(f"✅ [SUCCESS] Presentation verified: {verification_result.get('title', 'Untitled')}")
        
        # Export as PDF using Google Drive API
        # Note: Google Slides API doesn't directly support PDF export,
        # but Google Drive API's export_media endpoint supports it
        drive_service = build('drive', 'v3', credentials=creds)
        
        print(f"📥 [IN PROGRESS] Exporting presentation {presentation_id} as PDF via Google Drive API...")
        try:
            pdf_data = drive_service.files().export_media(
                fileId=presentation_id,
                mimeType='application/pdf'
            ).execute()
            print(f"✅ [SUCCESS] PDF export completed ({len(pdf_data)} bytes)")
            print(f"   PDF downloaded successfully from Google Slides")
            
            # Save PDF to output/pdf/ directory
            pdf_dir = Path(output_dir) / "pdf"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_file = pdf_dir / f"{presentation_id}.pdf"
            with open(pdf_file, 'wb') as f:
                f.write(pdf_data)
            print(f"   💾 PDF saved to: {pdf_file}")
            
        except HttpError as error:
            error_details = error.error_details if hasattr(error, 'error_details') else []
            error_msg = f"Failed to export PDF for presentation {presentation_id}. Error: {error}"
            print(f"❌ [FAILED] PDF export via Google Drive API: {error_msg}")
            print(f"   Error details: {error_details}")
            # Re-raise the original HttpError (it already has proper resp attribute)
            raise
        except Exception as e:
            print(f"❌ [FAILED] PDF export error: {e}")
            raise
        
    except FileNotFoundError as e:
        print(f"❌ [FAILED] Credentials not found: {e}")
        raise e
    except ValueError as e:
        # Handle ValueError from presentation verification
        print(f"❌ [FAILED] Presentation verification error: {e}")
        raise
    except HttpError as error:
        print(f"❌ [FAILED] Google API error: {error}")
        raise
    except Exception as e:
        print(f"❌ [FAILED] Unexpected error in PDF export: {e}")
        raise
    
    # Now check for pdf2image dependency (only needed for Step 2)
    print("\n" + "=" * 60)
    print("🖼️  STEP 2: Convert PDF to Images")
    print("=" * 60)
    
    # Check pdf2image availability at runtime (not at import time)
    try:
        from pdf2image import convert_from_bytes
        # Test that it's actually callable
        if convert_from_bytes is None:
            raise ImportError("convert_from_bytes is None")
        pdf2image_available = True
    except (ImportError, AttributeError) as e:
        pdf2image_available = False
        error_msg = (
            f"pdf2image is not installed. Install it with: pip install pdf2image Pillow\n"
            f"Also install poppler: brew install poppler (macOS) or sudo apt-get install poppler-utils (Linux)\n"
            f"Import error: {e}"
        )
        print(f"❌ [FAILED] Dependency check: {error_msg}")
        print(f"   Note: PDF was successfully downloaded ({len(pdf_data)} bytes), but cannot convert to images without pdf2image")
        raise ImportError(error_msg)
    
    print(f"✅ [SUCCESS] Dependency check: pdf2image and poppler available")
    
    try:
        # Convert PDF pages to images
        print(f"🖼️  [IN PROGRESS] Converting PDF to images using pdf2image...")
        try:
            images = convert_from_bytes(pdf_data, dpi=200)
            print(f"✅ [SUCCESS] PDF to image conversion completed ({len(images)} slides converted)")
        except Exception as e:
            print(f"❌ [FAILED] PDF to image conversion error: {e}")
            raise
        
        # Save images to output/img/ directory
        img_dir = Path(output_dir) / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        print(f"💾 [IN PROGRESS] Saving images to {img_dir}/...")
        
        # Convert PIL Images to bytes and save to disk
        print(f"📦 [IN PROGRESS] Converting PIL Images to bytes and saving to disk...")
        image_bytes_list = []
        for idx, image in enumerate(images, start=1):
            try:
                # Save image to disk
                img_filename = f"{presentation_id}_slide_{idx:03d}.png"
                img_path = img_dir / img_filename
                image.save(img_path, format='PNG')
                print(f"   💾 Slide {idx} saved to: {img_path}")
                
                # Also convert to bytes for in-memory processing
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                image_bytes_list.append(img_bytes.read())
                print(f"   ✅ Slide {idx} converted to PNG bytes ({len(image_bytes_list[-1])} bytes)")
            except Exception as e:
                print(f"   ❌ [FAILED] Failed to process slide {idx}: {e}")
                raise
        
        print(f"✅ [SUCCESS] All {len(image_bytes_list)} slides saved to {img_dir}/ and converted to bytes")
        return image_bytes_list
        
    except Exception as e:
        print(f"❌ [FAILED] Unexpected error in PDF to image conversion: {e}")
        raise


def detect_text_overlaps(word_data: List[Dict], min_overlap_ratio: float = 0.05, min_overlap_area: int = 50) -> List[Dict]:
    """
    Detect overlapping text bounding boxes.
    
    This is RULE-BASED (not prompt engineering):
    1. Vision API provides OCR bounding boxes for each word
    2. We check if bounding boxes overlap geometrically
    3. We filter out minor overlaps (OCR artifacts) using thresholds
    
    Args:
        word_data: List of dicts with 'text' and 'bounding_box' keys
        min_overlap_ratio: Minimum overlap ratio to consider it a real overlap (default: 0.05 = 5%)
                          This filters out tiny overlaps from OCR bounding box inaccuracies
        min_overlap_area: Minimum overlap area in pixels to consider it a real overlap (default: 50)
                          This filters out overlaps that are too small to be visible
        
    Returns:
        List of overlap detections
    """
    overlaps = []
    
    for i, word1 in enumerate(word_data):
        for j, word2 in enumerate(word_data[i+1:], start=i+1):
            box1 = word1['bounding_box']
            box2 = word2['bounding_box']
            
            # Check if boxes overlap geometrically
            if boxes_overlap(box1, box2):
                overlap_area = calculate_overlap_area(box1, box2)
                box1_area = (box1['x2'] - box1['x1']) * (box1['y2'] - box1['y1'])
                box2_area = (box2['x2'] - box2['x1']) * (box2['y2'] - box2['y1'])
                overlap_ratio = overlap_area / min(box1_area, box2_area) if min(box1_area, box2_area) > 0 else 0
                
                # Filter out minor overlaps (OCR artifacts)
                # Only report if overlap is significant enough to be visible
                if overlap_area >= min_overlap_area and overlap_ratio >= min_overlap_ratio:
                    overlaps.append({
                        'word1': word1['text'],
                        'word2': word2['text'],
                        'overlap_area': overlap_area,
                        'overlap_ratio': overlap_ratio,
                        'severity': 'critical' if overlap_ratio > 0.5 else 'major' if overlap_ratio > 0.2 else 'minor'
                    })
    
    return overlaps


def boxes_overlap(box1: Dict, box2: Dict) -> bool:
    """Check if two bounding boxes overlap."""
    return not (box1['x2'] < box2['x1'] or 
                box2['x2'] < box1['x1'] or 
                box1['y2'] < box2['y1'] or 
                box2['y2'] < box1['y1'])


def calculate_overlap_area(box1: Dict, box2: Dict) -> float:
    """Calculate overlap area between two bounding boxes."""
    x_overlap = max(0, min(box1['x2'], box2['x2']) - max(box1['x1'], box2['x1']))
    y_overlap = max(0, min(box1['y2'], box2['y2']) - max(box1['y1'], box2['y1']))
    return x_overlap * y_overlap


def check_text_overflow(words: List[Dict], image_width: int, image_height: int, margin: int = 20) -> List[Dict]:
    """
    Check if any text extends beyond image boundaries.
    
    Args:
        words: List of word data with bounding boxes
        image_width: Width of the image
        image_height: Height of the image
        margin: Margin to allow (pixels)
        
    Returns:
        List of overflow issues
    """
    overflow_issues = []
    
    for word in words:
        box = word['bounding_box']
        if (box['x1'] < margin or 
            box['x2'] > image_width - margin or
            box['y1'] < margin or
            box['y2'] > image_height - margin):
            overflow_issues.append({
                'text': word['text'],
                'bounding_box': box,
                'issue': 'Text extends beyond slide boundaries'
            })
    
    return overflow_issues


def analyze_slides_batch_gemini_vision(slide_images: List[bytes], presentation_id: str = "") -> List[Dict]:
    """
    Analyze multiple slide images using Gemini Vision API with prompts.
    This is PROMPT-BASED (not rule-based) - Gemini actually "sees" the images.
    
    Args:
        slide_images: List of image data as bytes (one per slide)
        presentation_id: Presentation ID for logging (optional)
        
    Returns:
        List of dicts with layout analysis results (one per slide)
    """
    if not GEMINI_VISION_AVAILABLE:
        error_msg = "google-genai is not installed. Install it with: pip install google-genai"
        print(f"❌ [FAILED] Gemini Vision API dependency check: {error_msg}")
        raise ImportError(error_msg)
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        error_msg = "GOOGLE_API_KEY environment variable not set"
        print(f"❌ [FAILED] {error_msg}")
        raise ValueError(error_msg)
    
    print(f"\n🔍 [GEMINI VISION MODE] Analyzing {len(slide_images)} slides with Gemini Vision API (prompt-based)...")
    
    try:
        # Initialize Gemini Vision client
        client = Client(api_key=api_key)
        print(f"   ✅ Gemini Vision client initialized")
        
        # Analyze each slide with Gemini Vision
        results = []
        for slide_num, image_bytes in enumerate(slide_images, start=1):
            print(f"   📊 [IN PROGRESS] Analyzing slide {slide_num}/{len(slide_images)} with Gemini Vision...")
            
            try:
                # Convert image bytes to base64
                image_base64 = base64.b64encode(image_bytes).decode()
                
                # Create prompt for layout analysis
                prompt = """Analyze this presentation slide image for layout issues. 

Check for:
1. **Text Overlap**: Are any text elements visually overlapping each other? (Not just bounding boxes - actual visible text overlap)
2. **Empty Slides**: Is this slide empty or mostly empty?
3. **Text Overflow**: Does any text extend beyond its container or slide boundaries?
4. **Spacing Issues**: Is there adequate whitespace between elements?
5. **Alignment Issues**: Are elements properly aligned?

IMPORTANT: 
- Focus on VISUAL overlap of actual text content, not just bounding box overlaps
- Consider that text boxes may have padding, so slight bounding box overlaps are normal
- Only report overlaps if the actual text characters are visually overlapping

Return a JSON object with this exact structure:
{
    "slide_number": <number>,
    "text_overlap_detected": <true/false>,
    "empty_slide": <true/false>,
    "text_overflow_detected": <true/false>,
    "spacing_issues": <true/false>,
    "alignment_issues": <true/false>,
    "issues": [
        {
            "type": "<text_overlap | empty_slide | text_overflow | spacing | alignment>",
            "description": "<detailed description>",
            "severity": "<critical | major | minor>"
        }
    ],
    "recommendations": ["<recommendation1>", "<recommendation2>"],
    "overall_quality": "<excellent | good | needs_improvement | poor>"
}

Return ONLY valid JSON, no markdown code blocks, no explanations."""
                
                # Call Gemini Vision API
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": image_base64
                                    }
                                }
                            ]
                        }
                    ]
                )
                
                # Parse response
                response_text = response.text.strip()
                
                # Remove markdown code blocks if present
                if response_text.startswith("```json"):
                    response_text = response_text[7:].lstrip()
                elif response_text.startswith("```"):
                    response_text = response_text[3:].lstrip()
                if response_text.endswith("```"):
                    response_text = response_text[:-3].rstrip()
                
                # Parse JSON
                try:
                    analysis = json.loads(response_text)
                    # Ensure slide_number is set
                    analysis['slide_number'] = slide_num
                    
                    # Convert to our standard format
                    overlaps = []
                    overflow_issues = []
                    
                    for issue in analysis.get('issues', []):
                        if issue.get('type') == 'text_overlap':
                            # Extract actual text from description if possible
                            description = issue.get('description', '')
                            # Try to extract text elements from description
                            # Format might be: "Title text overlaps with content text" or "Text 'X' overlaps with 'Y'"
                            word1_text = 'text_element_1'
                            word2_text = 'text_element_2'
                            
                            # Try to extract quoted text or specific mentions
                            quoted_texts = re.findall(r"'([^']+)'", description) or re.findall(r'"([^"]+)"', description)
                            if len(quoted_texts) >= 2:
                                word1_text = quoted_texts[0]
                                word2_text = quoted_texts[1]
                            elif len(quoted_texts) == 1:
                                word1_text = quoted_texts[0]
                                word2_text = 'another_text_element'
                            
                            # If no quotes, try to extract from common patterns
                            if word1_text == 'text_element_1':
                                # Look for patterns like "X overlaps with Y" or "Title overlaps with content"
                                overlap_pattern = re.search(r'(\w+(?:\s+\w+)*)\s+overlaps?\s+with\s+(\w+(?:\s+\w+)*)', description, re.IGNORECASE)
                                if overlap_pattern:
                                    word1_text = overlap_pattern.group(1)
                                    word2_text = overlap_pattern.group(2)
                            
                            overlaps.append({
                                'word1': word1_text,
                                'word2': word2_text,
                                'overlap_ratio': 0.5 if issue.get('severity') == 'critical' else 0.3 if issue.get('severity') == 'major' else 0.1,
                                'severity': issue.get('severity', 'minor'),
                                'description': description  # Keep full description for context
                            })
                        elif issue.get('type') == 'text_overflow':
                            overflow_issues.append({
                                'text': 'text_element',
                                'issue': issue.get('description', 'Text overflow detected')
                            })
                    
                    result = {
                        'slide_number': slide_num,
                        'text_detected': not analysis.get('empty_slide', False),
                        'full_text': '',  # Gemini Vision doesn't extract text, just analyzes layout
                        'word_count': 0,
                        'words': [],
                        'overlaps': overlaps,
                        'overflow_issues': overflow_issues,
                        'empty_slide': analysis.get('empty_slide', False),
                        'spacing_issues': analysis.get('spacing_issues', False),
                        'alignment_issues': analysis.get('alignment_issues', False),
                        'overall_quality': analysis.get('overall_quality', 'unknown'),
                        'recommendations': analysis.get('recommendations', []),
                        'gemini_analysis': analysis  # Keep full Gemini response
                    }
                    
                    results.append(result)
                    
                    if analysis.get('text_overlap_detected'):
                        print(f"   ⚠️  Slide {slide_num}: Text overlap detected")
                    elif analysis.get('empty_slide'):
                        print(f"   ⚠️  Slide {slide_num}: Empty slide detected")
                    else:
                        print(f"   ✅ Slide {slide_num}: No major issues detected")
                        
                except json.JSONDecodeError as e:
                    print(f"   ⚠️  Slide {slide_num}: Failed to parse Gemini response as JSON: {e}")
                    print(f"   Raw response: {response_text[:200]}...")
                    # Return empty result on parse error
                    results.append({
                        'slide_number': slide_num,
                        'text_detected': False,
                        'error': f'Failed to parse Gemini response: {e}',
                        'words': [],
                        'overlaps': [],
                        'overflow_issues': []
                    })
                    
            except Exception as e:
                print(f"   ❌ [FAILED] Error analyzing slide {slide_num} with Gemini Vision: {e}")
                results.append({
                    'slide_number': slide_num,
                    'text_detected': False,
                    'error': str(e),
                    'words': [],
                    'overlaps': [],
                    'overflow_issues': []
                })
        
        print(f"   ✅ [SUCCESS] Gemini Vision analysis completed for {len(results)} slides")
        return results
        
    except Exception as e:
        print(f"   ❌ [FAILED] Gemini Vision batch error: {e}")
        raise


def analyze_slides_batch_vision_api(slide_images: List[bytes]) -> List[Dict]:
    """
    Analyze multiple slide images using Google Cloud Vision API in a single batch request.
    This is more cost-effective than individual requests.
    
    Args:
        slide_images: List of image data as bytes (one per slide)
        
    Returns:
        List of dicts with text detection results and layout analysis (one per slide)
    """
    if not VISION_AVAILABLE:
        error_msg = "google-cloud-vision is not installed. Install it with: pip install google-cloud-vision"
        print(f"❌ [FAILED] Vision API dependency check: {error_msg}")
        raise ImportError(error_msg)
    
    print(f"\n🔍 [BATCH MODE] Analyzing {len(slide_images)} slides in a single Vision API batch request...")
    
    try:
        # Initialize Vision API client
        try:
            creds = get_credentials()
            client = vision.ImageAnnotatorClient(credentials=creds)
            print(f"   ✅ Vision API client initialized with OAuth credentials")
        except Exception as e:
            print(f"   ⚠️  OAuth credentials not available, using default credentials: {e}")
            client = vision.ImageAnnotatorClient()
            print(f"   ✅ Vision API client initialized with default credentials")
        
        # Prepare batch request - create image objects for all slides
        requests = []
        for image_bytes in slide_images:
            image = vision.Image(content=image_bytes)
            request = vision.AnnotateImageRequest(
                image=image,
                features=[vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION)]
            )
            requests.append(request)
        
        # Perform batch text detection (all slides in one API call)
        print(f"   📊 [IN PROGRESS] Calling Vision API batch_annotate_images for {len(requests)} slides...")
        try:
            batch_request = vision.BatchAnnotateImagesRequest(requests=requests)
            response = client.batch_annotate_images(request=batch_request)
            print(f"   ✅ [SUCCESS] Vision API batch request completed")
        except Exception as e:
            print(f"   ❌ [FAILED] Vision API batch request error: {e}")
            raise
        
        # Process results - map back to individual slides
        results = []
        for slide_num, (image_bytes, annotate_response) in enumerate(zip(slide_images, response.responses), start=1):
            if annotate_response.error.message:
                print(f"   ⚠️  Error on slide {slide_num}: {annotate_response.error.message}")
                results.append({
                    'slide_number': slide_num,
                    'text_detected': False,
                    'error': annotate_response.error.message,
                    'words': [],
                    'overlaps': [],
                    'overflow_issues': []
                })
                continue
            
            texts = annotate_response.text_annotations
            
            if not texts:
                print(f"   ⚠️  No text detected in slide {slide_num}")
                results.append({
                    'slide_number': slide_num,
                    'text_detected': False,
                    'words': [],
                    'overlaps': [],
                    'overflow_issues': []
                })
                continue
            
            # First annotation contains all text
            full_text = texts[0].description
            
            # Remaining annotations are individual words with bounding boxes
            word_data = []
            for text in texts[1:]:
                vertices = text.bounding_poly.vertices
                if len(vertices) >= 4:
                    word_data.append({
                        'text': text.description,
                        'bounding_box': {
                            'x1': vertices[0].x,
                            'y1': vertices[0].y,
                            'x2': vertices[2].x if len(vertices) > 2 else vertices[0].x,
                            'y2': vertices[2].y if len(vertices) > 2 else vertices[0].y,
                        }
                    })
            
            # Detect overlaps
            overlaps = detect_text_overlaps(word_data)
            
            # Get image dimensions
            if word_data:
                max_x = max(w['bounding_box']['x2'] for w in word_data)
                max_y = max(w['bounding_box']['y2'] for w in word_data)
                image_width = max_x + 100
                image_height = max_y + 100
            else:
                image_width = 1920
                image_height = 1080
            
            # Check for text overflow
            overflow_issues = check_text_overflow(word_data, image_width, image_height)
            
            results.append({
                'slide_number': slide_num,
                'text_detected': True,
                'full_text': full_text,
                'word_count': len(word_data),
                'words': word_data,
                'overlaps': overlaps,
                'overflow_issues': overflow_issues,
                'estimated_dimensions': {
                    'width': image_width,
                    'height': image_height
                }
            })
            
            if overlaps:
                print(f"   ⚠️  Slide {slide_num}: Found {len(overlaps)} text overlap(s)")
            else:
                print(f"   ✅ Slide {slide_num}: No overlaps detected ({len(word_data)} words)")
        
        print(f"   ✅ [SUCCESS] Batch analysis completed for {len(results)} slides")
        return results
        
    except Exception as e:
        print(f"   ❌ [FAILED] Vision API batch error: {e}")
        raise


def analyze_slide_with_vision_api(image_bytes: bytes, slide_num: int = 0) -> Dict:
    """
    Analyze slide image using Google Cloud Vision API (VLM).
    
    Args:
        image_bytes: Image data as bytes
        slide_num: Slide number for logging (optional)
        
    Returns:
        Dict with text detection results and layout analysis
    """
    if not VISION_AVAILABLE:
        error_msg = "google-cloud-vision is not installed. Install it with: pip install google-cloud-vision"
        print(f"❌ [FAILED] Vision API dependency check: {error_msg}")
        raise ImportError(error_msg)
    
    print(f"   🔍 [IN PROGRESS] Analyzing slide {slide_num} with Vision API (VLM)...")
    
    try:
        # Initialize Vision API client
        # Try to use the same credentials as Slides API, or use default
        try:
            # Try to use existing credentials
            creds = get_credentials()
            # Vision API can use the same OAuth credentials
            client = vision.ImageAnnotatorClient(credentials=creds)
            print(f"   ✅ Vision API client initialized with OAuth credentials")
        except Exception as e:
            # Fall back to default credentials (GOOGLE_APPLICATION_CREDENTIALS or gcloud auth)
            print(f"   ⚠️  OAuth credentials not available, using default credentials: {e}")
            client = vision.ImageAnnotatorClient()
            print(f"   ✅ Vision API client initialized with default credentials")
        
        # Create image object
        image = vision.Image(content=image_bytes)
        
        # Perform text detection (OCR) using Vision API
        print(f"   📊 [IN PROGRESS] Calling Vision API text_detection...")
        try:
            response = client.text_detection(image=image)
            texts = response.text_annotations
            print(f"   ✅ [SUCCESS] Vision API text detection completed")
        except Exception as e:
            print(f"   ❌ [FAILED] Vision API text detection error: {e}")
            raise
        
        if not texts:
            print(f"   ⚠️  No text detected in slide {slide_num}")
            return {
                'text_detected': False,
                'words': [],
                'overlaps': [],
                'overflow_issues': []
            }
        
        # First annotation contains all text
        full_text = texts[0].description
        
        # Remaining annotations are individual words with bounding boxes
        word_data = []
        for text in texts[1:]:
            vertices = text.bounding_poly.vertices
            if len(vertices) >= 4:
                word_data.append({
                    'text': text.description,
                    'bounding_box': {
                        'x1': vertices[0].x,
                        'y1': vertices[0].y,
                        'x2': vertices[2].x if len(vertices) > 2 else vertices[0].x,
                        'y2': vertices[2].y if len(vertices) > 2 else vertices[0].y,
                    }
                })
        
        print(f"   ✅ Extracted {len(word_data)} words from slide {slide_num}")
        
        # Detect overlaps
        print(f"   🔍 [IN PROGRESS] Detecting text overlaps...")
        overlaps = detect_text_overlaps(word_data)
        if overlaps:
            print(f"   ⚠️  Found {len(overlaps)} text overlap(s) on slide {slide_num}")
        else:
            print(f"   ✅ No text overlaps detected on slide {slide_num}")
        
        # Get image dimensions (approximate from bounding boxes)
        if word_data:
            max_x = max(w['bounding_box']['x2'] for w in word_data)
            max_y = max(w['bounding_box']['y2'] for w in word_data)
            # Estimate image size (Vision API doesn't provide it directly)
            # Use a reasonable default or calculate from bounding boxes
            image_width = max_x + 100  # Add margin
            image_height = max_y + 100
        else:
            image_width = 1920  # Default slide width
            image_height = 1080  # Default slide height
        
        # Check for text overflow
        print(f"   🔍 [IN PROGRESS] Checking text overflow...")
        overflow_issues = check_text_overflow(word_data, image_width, image_height)
        if overflow_issues:
            print(f"   ⚠️  Found {len(overflow_issues)} text overflow issue(s) on slide {slide_num}")
        else:
            print(f"   ✅ No text overflow detected on slide {slide_num}")
        
        print(f"   ✅ [SUCCESS] Slide {slide_num} analysis completed")
        
        return {
            'text_detected': True,
            'full_text': full_text,
            'word_count': len(word_data),
            'words': word_data,
            'overlaps': overlaps,
            'overflow_issues': overflow_issues,
            'estimated_dimensions': {
                'width': image_width,
                'height': image_height
            }
        }
        
    except Exception as e:
        print(f"   ❌ [FAILED] Vision API error on slide {slide_num}: {e}")
        # Return empty result if Vision API fails
        return {
            'text_detected': False,
            'error': str(e),
            'words': [],
            'overlaps': [],
            'overflow_issues': []
        }


def review_slides_layout(presentation_id: str, output_dir: str = "presentation_agent/output") -> Dict:
    """
    Review Google Slides presentation for layout issues using Vision API.
    
    Steps:
    1. Export slides as images
    2. Analyze each image with Vision API
    3. Detect overlaps and layout issues
    4. Return comprehensive review
    
    Args:
        presentation_id: Google Slides presentation ID
        output_dir: Output directory for saving PDFs (default: "output")
        
    Returns:
        Dict with layout review results
    """
    try:
        print(f"\n🔍 Starting layout review for presentation: {presentation_id}")
        
        # Validate presentation_id format (should be numeric string)
        if not presentation_id or not isinstance(presentation_id, str):
            return {
                'review_type': 'layout_vision_api',
                'presentation_id': presentation_id,
                'error': f'Invalid presentation_id: {presentation_id} (must be a non-empty string)',
                'total_slides_reviewed': 0,
                'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                'issues': [],
                'overall_quality': 'unknown',
                'passed': False
            }
        
        # Step 1: Export slides as images (PDF export + PDF to image conversion)
        slide_images = export_slides_as_images(presentation_id, output_dir=output_dir)
        
        print("\n" + "=" * 60)
        print("🤖 STEP 3: Analyze Slides for Layout Issues")
        print("=" * 60)
        
        # Step 2: Analyze slides with Gemini Vision API (prompt-based, visual analysis)
        if not GEMINI_VISION_AVAILABLE:
            error_msg = "google-genai is not installed. Install it with: pip install google-genai"
            print(f"❌ [FAILED] {error_msg}")
            raise ImportError(error_msg)
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            error_msg = "GOOGLE_API_KEY environment variable not set"
            print(f"❌ [FAILED] {error_msg}")
            raise ValueError(error_msg)
        
        # Validate slide_images is not None
        if slide_images is None:
            error_msg = "Failed to export slides as images - slide_images is None"
            print(f"❌ [FAILED] {error_msg}")
            raise ValueError(error_msg)
        
        print(f"📊 Analyzing {len(slide_images)} slides with Gemini Vision API (prompt-based, visual analysis)...")
        batch_results = analyze_slides_batch_gemini_vision(slide_images, presentation_id=presentation_id)
        
        # Validate batch_results is not None
        if batch_results is None:
            error_msg = "Gemini Vision analysis returned None"
            print(f"❌ [FAILED] {error_msg}")
            raise ValueError(error_msg)
        
        # Step 3: Process batch results and collect issues
        all_issues = []
        for analysis in batch_results:
            # Skip None or invalid analysis results
            if not analysis or not isinstance(analysis, dict):
                print(f"   ⚠️  Skipping invalid analysis result: {type(analysis).__name__}")
                continue
            
            slide_num = analysis.get('slide_number', 0)
            
            # Collect issues
            slide_issues = []
            
            # Handle overlaps (from both Gemini Vision and Vision API)
            overlaps = analysis.get('overlaps')
            if overlaps and isinstance(overlaps, list):
                slide_issues.append({
                    'type': 'text_overlap',
                    'count': len(overlaps),
                    'details': overlaps
                })
            
            # Handle overflow issues
            overflow_issues = analysis.get('overflow_issues')
            if overflow_issues and isinstance(overflow_issues, list):
                slide_issues.append({
                    'type': 'text_overflow',
                    'count': len(overflow_issues),
                    'details': overflow_issues
                })
            
            # Handle empty slides (from Gemini Vision)
            if analysis.get('empty_slide'):
                slide_issues.append({
                    'type': 'empty_slide',
                    'count': 1,
                    'details': [{'description': 'Slide appears to be empty or mostly empty'}]
                })
            
            # Handle spacing issues (from Gemini Vision)
            if analysis.get('spacing_issues'):
                slide_issues.append({
                    'type': 'spacing',
                    'count': 1,
                    'details': [{'description': 'Inadequate whitespace between elements'}]
                })
            
            # Handle alignment issues (from Gemini Vision)
            if analysis.get('alignment_issues'):
                slide_issues.append({
                    'type': 'alignment',
                    'count': 1,
                    'details': [{'description': 'Elements are not properly aligned'}]
                })
            
            if slide_issues:
                all_issues.append({
                    'slide_number': slide_num,
                    'issues': slide_issues,
                    'word_count': analysis.get('word_count', 0)
                })
        
        # Step 3: Generate summary
        total_overlaps = sum(
            sum(issue['count'] for issue in slide['issues'] if issue['type'] == 'text_overlap')
            for slide in all_issues
        )
        total_overflow = sum(
            sum(issue['count'] for issue in slide['issues'] if issue['type'] == 'text_overflow')
            for slide in all_issues
        )
        
        # Count severity levels for overlaps
        critical_overlaps = 0
        major_overlaps = 0
        minor_overlaps = 0
        
        for slide in all_issues:
            for issue in slide['issues']:
                if issue['type'] == 'text_overlap':
                    for detail in issue.get('details', []):
                        severity = detail.get('severity', 'minor')
                        if severity == 'critical':
                            critical_overlaps += 1
                        elif severity == 'major':
                            major_overlaps += 1
                        else:
                            minor_overlaps += 1
        
        # Pass/fail rule: Pass only if there are NO text overlap issues
        # (Overflow issues are tracked but don't affect pass/fail for now)
        passed = (total_overlaps == 0)
        total_issues = total_overlaps + total_overflow
        
        print("\n" + "=" * 60)
        print("📊 STEP 4: Generate Layout Review Summary")
        print("=" * 60)
        print(f"✅ [SUCCESS] Layout review completed")
        print(f"   Total slides reviewed: {len(slide_images)}")
        print(f"   Slides with issues: {len(all_issues)}")
        print(f"   Total overlaps: {total_overlaps}")
        print(f"   Total overflow issues: {total_overflow}")
        print(f"   Overall quality: {'excellent' if len(all_issues) == 0 else 'needs_improvement' if len(all_issues) < 3 else 'poor'}")
        print(f"   Passed: {'✅ YES' if passed else '❌ NO'}")
        print("=" * 60)
        
        return {
            'review_type': 'layout_vision_api',
            'presentation_id': presentation_id,
            'total_slides_reviewed': len(slide_images),
            'total_slides': len(slide_images),
            'issues_found': len(all_issues),
            'total_overlaps': total_overlaps,
            'total_overflow': total_overflow,
            'issues_summary': {
                'total_issues': total_issues,
                'overlaps_detected': total_overlaps,
                'overflow_detected': total_overflow,
                'overlap_severity': {
                    'critical': critical_overlaps,
                    'major': major_overlaps,
                    'minor': minor_overlaps
                }
            },
            'overlap_severity': {
                'critical': critical_overlaps,
                'major': major_overlaps,
                'minor': minor_overlaps
            },
            'issues': all_issues,
            'overall_quality': 'excellent' if len(all_issues) == 0 else 'needs_improvement' if len(all_issues) < 3 else 'poor',
            'passed': passed  # Explicit pass/fail: true only if no text overlaps
        }
        
    except Exception as e:
        print(f"❌ Error in layout review: {e}")
        return {
            'review_type': 'layout_vision_api',
            'presentation_id': presentation_id,
            'error': str(e),
            'total_slides_reviewed': 0,
            'total_slides': 0,
            'issues_summary': {
                'total_issues': 0,
                'overlaps_detected': 0,
                'overflow_detected': 0,
                'overlap_severity': {
                    'critical': 0,
                    'major': 0,
                    'minor': 0
                }
            },
            'issues': [],
            'overall_quality': 'unknown',
            'passed': False
        }

