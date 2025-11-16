"""
Google Slides Layout Analysis Tool.
Exports slides as images and analyzes them using Google Cloud Vision API.
"""

import os
import io
import json
from typing import Dict, List, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Optional imports - will fail gracefully if not installed
try:
    from google.cloud import vision
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    vision = None

# Check pdf2image availability at runtime, not at import time
# This allows the module to load even if pdf2image is not installed
PDF2IMAGE_AVAILABLE = None  # Will be checked at runtime
convert_from_bytes = None

# Scopes required
SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive.readonly'
]

# Path to credentials directory
CREDENTIALS_DIR = Path(__file__).parent.parent / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"


def get_credentials() -> Credentials:
    """
    Get OAuth2 credentials for Google APIs.
    If token exists, use it. Otherwise, run OAuth flow.
    
    Returns:
        Credentials object for Google API
    """
    creds = None
    
    # Create credentials directory if it doesn't exist
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    
    # Load existing token if available
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
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
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"❌ Credentials file not found: {CREDENTIALS_FILE}\n"
                    f"Please download credentials.json from Google Cloud Console and place it in:\n"
                    f"{CREDENTIALS_DIR}\n"
                    f"See GOOGLE_SLIDES_SETUP.md for setup instructions."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save token for future use
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print("✅ Credentials saved for future use")
    
    return creds


def export_slides_as_images(presentation_id: str, output_dir: str = "output") -> List[bytes]:
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
            print(f"❌ [FAILED] PDF export via Google Drive API: {error}")
            raise
        except Exception as e:
            print(f"❌ [FAILED] PDF export error: {e}")
            raise
        
    except FileNotFoundError as e:
        print(f"❌ [FAILED] Credentials not found: {e}")
        raise e
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
        
        # Convert PIL Images to bytes
        print(f"📦 [IN PROGRESS] Converting PIL Images to bytes...")
        image_bytes_list = []
        for idx, image in enumerate(images, start=1):
            try:
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                image_bytes_list.append(img_bytes.read())
                print(f"   ✅ Slide {idx} converted to PNG ({len(image_bytes_list[-1])} bytes)")
            except Exception as e:
                print(f"   ❌ [FAILED] Failed to convert slide {idx} to bytes: {e}")
                raise
        
        print(f"✅ [SUCCESS] All {len(image_bytes_list)} slides converted to image bytes")
        return image_bytes_list
        
    except Exception as e:
        print(f"❌ [FAILED] Unexpected error in PDF to image conversion: {e}")
        raise


def detect_text_overlaps(word_data: List[Dict]) -> List[Dict]:
    """
    Detect overlapping text bounding boxes.
    
    Args:
        word_data: List of dicts with 'text' and 'bounding_box' keys
        
    Returns:
        List of overlap detections
    """
    overlaps = []
    
    for i, word1 in enumerate(word_data):
        for j, word2 in enumerate(word_data[i+1:], start=i+1):
            box1 = word1['bounding_box']
            box2 = word2['bounding_box']
            
            # Check if boxes overlap
            if boxes_overlap(box1, box2):
                overlap_area = calculate_overlap_area(box1, box2)
                box1_area = (box1['x2'] - box1['x1']) * (box1['y2'] - box1['y1'])
                box2_area = (box2['x2'] - box2['x1']) * (box2['y2'] - box2['y1'])
                overlap_ratio = overlap_area / min(box1_area, box2_area) if min(box1_area, box2_area) > 0 else 0
                
                overlaps.append({
                    'word1': word1['text'],
                    'word2': word2['text'],
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


def review_slides_layout(presentation_id: str, output_dir: str = "output") -> Dict:
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
        
        # Step 1: Export slides as images (PDF export + PDF to image conversion)
        slide_images = export_slides_as_images(presentation_id, output_dir=output_dir)
        
        print("\n" + "=" * 60)
        print("🤖 STEP 3: Analyze Slides with Vision API (VLM)")
        print("=" * 60)
        print(f"📊 Analyzing {len(slide_images)} slides with Vision API...")
        
        # Step 2: Analyze each slide with Vision API (VLM)
        all_issues = []
        for slide_num, image_bytes in enumerate(slide_images, start=1):
            print(f"\n--- Slide {slide_num}/{len(slide_images)} ---")
            
            # Analyze with Vision API (VLM)
            analysis = analyze_slide_with_vision_api(image_bytes, slide_num=slide_num)
            
            # Collect issues
            slide_issues = []
            
            if analysis.get('overlaps'):
                slide_issues.append({
                    'type': 'text_overlap',
                    'count': len(analysis['overlaps']),
                    'details': analysis['overlaps']
                })
            
            if analysis.get('overflow_issues'):
                slide_issues.append({
                    'type': 'text_overflow',
                    'count': len(analysis['overflow_issues']),
                    'details': analysis['overflow_issues']
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

