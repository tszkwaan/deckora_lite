"""
Google Slides Exporter.
Exports slide deck and script to Google Slides using Google Slides API.
"""

import os
import json
import re
import tempfile
from pathlib import Path
from typing import Dict, Optional, List, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes required for Google Slides API
# Also include drive.readonly for PDF export (used by layout review)
# And cloud-platform for Vision API (used by layout review)
SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/cloud-platform'  # Required for Vision API (layout review)
]

# Path to credentials directory
CREDENTIALS_DIR = Path(__file__).parent.parent / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"


def get_credentials() -> Credentials:
    """
    Get OAuth2 credentials for Google Slides API.
    If token exists, use it. Otherwise, run OAuth flow.
    
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
        
        # Validate token.json is valid JSON before trying to load
        try:
            import json
            with open(TOKEN_FILE, 'r') as f:
                token_content = f.read()
                # Try to parse as JSON
                json.loads(token_content)
                logger.info("✅ Token file is valid JSON")
        except json.JSONDecodeError as e:
            error_msg = (
                f"❌ Token file is not valid JSON: {e}\n"
                f"File path: {TOKEN_FILE}\n"
                f"First 200 chars: {token_content[:200] if 'token_content' in locals() else 'N/A'}\n"
                f"Please check GitHub Secret GOOGLE_TOKEN_JSON contains valid JSON."
            )
            logger.error(error_msg)
            print(error_msg)
            token_file_path = None  # Don't try to load invalid JSON
        except Exception as e:
            logger.warning(f"⚠️  Could not validate token file: {e}")
    else:
        logger.warning(f"⚠️  Token file not found: {TOKEN_FILE}")
        logger.warning("   Please ensure GitHub Secret GOOGLE_TOKEN_JSON is set.")
    
    # Load existing token if available
    if token_file_path:
        try:
            creds = Credentials.from_authorized_user_file(token_file_path, SCOPES)
            logger.info("✅ Successfully loaded credentials from token file")
        except Exception as e:
            error_msg = f"⚠️  Warning: Could not load token: {e}"
            logger.error(error_msg)
            print(error_msg)
            creds = None
    
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
                    f"Please ensure GitHub Secret GOOGLE_CREDENTIALS_JSON is set.\n"
                    f"Files should be created during Docker build from GitHub Secrets."
                )
                raise FileNotFoundError(error_msg)
            
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file_path, SCOPES
            )
            # In Cloud Run, we can't run local server, so use console flow
            if os.environ.get('PORT'):  # Running in Cloud Run
                print("⚠️  Running in Cloud Run - OAuth flow requires manual setup")
                print("   Please ensure GitHub Secret GOOGLE_TOKEN_JSON is set.")
                raise RuntimeError(
                    "OAuth flow cannot run interactively in Cloud Run. "
                    "Please ensure GitHub Secret GOOGLE_TOKEN_JSON is set and files are created during Docker build."
                )
            creds = flow.run_local_server(port=0)
        
        # Save token for future use (only if not in Cloud Run)
        if not os.environ.get('PORT'):
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            print("✅ Credentials saved for future use")
    
    return creds


def parse_markdown_formatting(text: str) -> Tuple[str, List[Dict]]:
    """
    Parse markdown-style formatting and return plain text with style ranges.
    
    Handles:
    - **text** for bold
    - *text* for italic (but not **text**)
    - Nested formatting like **bold *italic* bold**
    
    Args:
        text: Text with markdown formatting (e.g., "**bold**", "*italic*")
        
    Returns:
        Tuple of (plain_text, style_ranges)
        style_ranges: List of dicts with format:
            {
                'start_index': int,
                'end_index': int,
                'bold': bool,
                'italic': bool
            }
    """
    if not text:
        return "", []
    
    style_ranges = []
    plain_text = ""
    i = 0
    
    while i < len(text):
        # Check for bold **text**
        if i + 1 < len(text) and text[i:i+2] == '**':
            # Find closing **
            end = text.find('**', i + 2)
            if end != -1:
                # Extract bold text (without markers)
                bold_text = text[i+2:end]
                start_idx = len(plain_text)
                
                # Check if bold text contains italic and process it
                italic_ranges = []
                bold_plain = ""
                j = 0
                while j < len(bold_text):
                    if j < len(bold_text) and bold_text[j] == '*' and (j == 0 or bold_text[j-1] != '*'):
                        # Find closing * (but not **)
                        italic_end = bold_text.find('*', j + 1)
                        if italic_end != -1:
                            # Check if it's not part of **
                            if italic_end + 1 >= len(bold_text) or bold_text[italic_end + 1] != '*':
                                italic_text = bold_text[j+1:italic_end]
                                italic_start = len(bold_plain)
                                bold_plain += italic_text
                                italic_end_pos = len(bold_plain)
                                italic_ranges.append({
                                    'start': italic_start,
                                    'end': italic_end_pos
                                })
                                j = italic_end + 1
                                continue
                    bold_plain += bold_text[j]
                    j += 1
                
                # Use bold_plain (with italic markers removed) instead of bold_text
                plain_text += bold_plain
                end_idx = len(plain_text)
                
                # Add bold range for entire text
                style_ranges.append({
                    'start_index': start_idx,
                    'end_index': end_idx,
                    'bold': True,
                    'italic': False
                })
                
                # Add italic ranges within bold (adjusted for position in plain_text)
                for italic_range in italic_ranges:
                    style_ranges.append({
                        'start_index': start_idx + italic_range['start'],
                        'end_index': start_idx + italic_range['end'],
                        'bold': True,
                        'italic': True
                    })
                
                i = end + 2
                continue
        
        # Check for italic *text* (but not **text**)
        if text[i] == '*' and (i == 0 or text[i-1] != '*') and (i + 1 >= len(text) or text[i+1] != '*'):
            # Find closing *
            end = text.find('*', i + 1)
            if end != -1 and (end + 1 >= len(text) or text[end+1] != '*'):
                # Extract italic text (without markers)
                italic_text = text[i+1:end]
                start_idx = len(plain_text)
                plain_text += italic_text
                end_idx = len(plain_text)
                
                style_ranges.append({
                    'start_index': start_idx,
                    'end_index': end_idx,
                    'bold': False,
                    'italic': True
                })
                
                i = end + 1
                continue
        
        # Regular character
        plain_text += text[i]
        i += 1
    
    return plain_text, style_ranges


def limit_title_to_lines(title: str, max_lines: int = 2, max_chars_per_line: int = 60) -> str:
    """
    Limit title to max_lines by truncating or splitting.
    
    Args:
        title: Original title text
        max_lines: Maximum number of lines allowed
        max_chars_per_line: Approximate characters per line
        
    Returns:
        Truncated title (with ellipsis if truncated)
    """
    if not title:
        return ""
    
    # If title is short enough, return as is
    if len(title) <= max_lines * max_chars_per_line:
        return title
    
    # Try to split at word boundaries
    words = title.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if len(test_line) <= max_chars_per_line:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                if len(lines) >= max_lines:
                    # Truncate remaining
                    remaining = " ".join([word] + words[words.index(word)+1:])
                    if len(remaining) > max_chars_per_line - 3:
                        remaining = remaining[:max_chars_per_line-3] + "..."
                    lines.append(remaining)
                    return "\n".join(lines)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    # If still too long, truncate
    result = "\n".join(lines[:max_lines])
    if len(lines) > max_lines or len(result) > max_lines * max_chars_per_line:
        result = result[:max_lines * max_chars_per_line - 3] + "..."
    
    return result


def find_text_shape_id(slide: Dict, shape_type: str = "TITLE") -> Optional[str]:
    """
    Find the object ID of a text shape in a slide.
    
    Args:
        slide: Slide object from Google Slides API
        shape_type: Type of shape to find ("TITLE", "BODY", "CENTERED_TITLE", "SUBTITLE")
        
    Returns:
        Object ID of the shape, or None if not found
    """
    # Google Slides uses these placeholder types:
    # - TITLE: Regular title placeholder
    # - CENTERED_TITLE: Centered title (for title slides)
    # - SUBTITLE: Subtitle (for title slides)
    # - BODY: Body/content placeholder
    
    # Handle special cases for title slides
    if shape_type == "TITLE":
        # Try both TITLE and CENTERED_TITLE
        for page_element in slide.get('pageElements', []):
            shape = page_element.get('shape', {})
            if shape:
                placeholder = shape.get('placeholder', {})
                placeholder_type = placeholder.get('type')
                if placeholder_type in ['TITLE', 'CENTERED_TITLE']:
                    return page_element.get('objectId')
        return None
    else:
        # For BODY, SUBTITLE, and other types, match exactly
        for page_element in slide.get('pageElements', []):
            shape = page_element.get('shape', {})
            if shape:
                placeholder = shape.get('placeholder', {})
                if placeholder.get('type') == shape_type:
                    return page_element.get('objectId')
        return None


def export_to_google_slides(
    slide_deck: Dict,
    presentation_script: Dict,
    config,
    title: str = "Generated Presentation"
) -> Dict[str, str]:
    """
    Export slide deck and script to Google Slides.
    
    Args:
        slide_deck: Slide deck JSON from slide generator
        presentation_script: Script JSON from script generator
        config: PresentationConfig object
        title: Presentation title
        
    Returns:
        Dict with presentation_id and shareable_url
        
    Raises:
        FileNotFoundError: If credentials.json is not found
        HttpError: If Google API call fails
    """
    presentation_id = None  # Initialize to track if presentation was created
    try:
        # Get credentials
        creds = get_credentials()
        
        # Log which account is being used
        import logging
        logger = logging.getLogger(__name__)
        if hasattr(creds, 'token') and 'email' in creds.token:
            account_email = creds.token.get('email', 'unknown')
            logger.info(f"📧 Using Google account: {account_email}")
            print(f"📧 Using Google account: {account_email}")
        elif hasattr(creds, 'id_token') and creds.id_token:
            # Try to extract email from id_token
            try:
                import base64
                import json
                # id_token is a JWT, decode the payload (second part)
                parts = creds.id_token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    # Add padding if needed
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += '=' * padding
                    decoded = json.loads(base64.urlsafe_b64decode(payload))
                    account_email = decoded.get('email', 'unknown')
                    logger.info(f"📧 Using Google account: {account_email}")
                    print(f"📧 Using Google account: {account_email}")
            except:
                logger.info("📧 Using Google account: (could not determine email)")
                print("📧 Using Google account: (could not determine email)")
        else:
            logger.info("📧 Using Google account: (could not determine email)")
            print("📧 Using Google account: (could not determine email)")
        
        # Build service
        service = build('slides', 'v1', credentials=creds)
        
        # Create presentation
        logger.info("📊 Creating Google Slides presentation...")
        print("📊 Creating Google Slides presentation...")
        try:
            presentation = service.presentations().create(
                body={'title': title}
            ).execute()
            presentation_id = presentation.get('presentationId')
            
            # Validate presentation_id was actually created
            if not presentation_id:
                error_msg = f"Failed to get presentation_id from Google Slides API response. Response: {presentation}"
                logger.error(f"❌ {error_msg}")
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            logger.info(f"✅ Presentation created: {presentation_id}")
            logger.info(f"   Full API response keys: {list(presentation.keys())}")
            print(f"✅ Presentation created: {presentation_id}")
            print(f"   Full API response keys: {list(presentation.keys())}")
            
            # Verify the presentation exists by trying to get it
            try:
                verify_presentation = service.presentations().get(
                    presentationId=presentation_id
                ).execute()
                print(f"✅ Verified presentation exists and is accessible")
            except HttpError as verify_error:
                print(f"⚠️  Warning: Could not verify presentation immediately: {verify_error}")
                # Continue anyway - might be a timing issue
                
        except HttpError as create_error:
            error_details = str(create_error)
            print(f"❌ Failed to create Google Slides presentation: {error_details}")
            # Try to extract more details from the error
            if hasattr(create_error, 'content'):
                print(f"   Error content: {create_error.content}")
            if hasattr(create_error, 'resp'):
                print(f"   Error response status: {getattr(create_error.resp, 'status', 'N/A')}")
            raise
        
        # Get presentation to access slides
        presentation = service.presentations().get(
            presentationId=presentation_id
        ).execute()
        
        # Build batch update requests
        requests = []
        
        # Create a mapping of slide_number to script section
        script_map = {}
        for section in presentation_script.get('script_sections', []):
            script_map[section.get('slide_number')] = section
        
        # Process each slide - create slides and add content in one pass
        slides = slide_deck.get('slides', [])
        print(f"📝 Processing {len(slides)} slides...")
        
        # Get the presentation to access the default title slide
        presentation = service.presentations().get(
            presentationId=presentation_id
        ).execute()
        slides_list = presentation.get('slides', [])
        
        # Build all requests for creating slides and adding content
        all_requests = []
        slide_object_ids = []  # Will store slide object IDs from response
        
        # For the first slide, we'll update the default title slide (index 0) instead of creating a new one
        # For remaining slides, create new ones starting at index 1
        for idx, slide_data in enumerate(slides):
            slide_number = slide_data.get('slide_number', idx + 1)
            
            if idx == 0:
                # Skip creating the first slide - we'll update the default title slide instead
                continue
            
            # Determine layout for remaining slides
            layout = 'TITLE_AND_BODY'
            
            # Create slide request (insert at index idx, since we're skipping the first one)
            all_requests.append({
                'createSlide': {
                    'slideLayoutReference': {
                        'predefinedLayout': layout
                    },
                    'insertionIndex': idx  # Insert at idx (which becomes 1, 2, 3, etc. after the default slide)
                }
            })
        
        # Execute slide creation (only for slides 2+)
        if all_requests:
            print("📊 Creating additional slides...")
            response = service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': all_requests}
            ).execute()
            
            # Extract slide object IDs from response
            for create_response in response.get('replies', []):
                if 'createSlide' in create_response:
                    slide_object_ids.append(create_response['createSlide']['objectId'])
        
        # Get updated presentation to access slide details
        presentation = service.presentations().get(
            presentationId=presentation_id
        ).execute()
        slides_list = presentation.get('slides', [])
        
        print(f"📊 Found {len(slides_list)} slides in presentation")
        
        # Now add content to each slide
        content_requests = []
        
        # Process all slides - first slide uses the default slide at index 0
        for idx, slide_data in enumerate(slide_deck.get('slides', [])):
            # First slide uses index 0 (the default title slide)
            # Remaining slides use index idx (1, 2, 3, etc.)
            slide_index = idx
            if slide_index >= len(slides_list):
                print(f"⚠️  Warning: Slide index {slide_index} out of range (max: {len(slides_list) - 1})")
                continue
            
            slide = slides_list[slide_index]
            slide_number = slide_data.get('slide_number', idx + 1)
            slide_title = slide_data.get('title', '')
            content = slide_data.get('content', {})
            bullet_points = content.get('bullet_points', [])
            main_text = content.get('main_text')
            
            # Find title and content shapes
            # For first slide (title slide), use CENTERED_TITLE and SUBTITLE
            if idx == 0:
                # Try CENTERED_TITLE first (most common for title slides)
                title_shape_id = find_text_shape_id(slide, 'CENTERED_TITLE')
                if not title_shape_id:
                    # Fall back to TITLE if CENTERED_TITLE not found
                    title_shape_id = find_text_shape_id(slide, 'TITLE')
                # Title slides use SUBTITLE for content, not BODY
                content_shape_id = find_text_shape_id(slide, 'SUBTITLE')
            else:
                title_shape_id = find_text_shape_id(slide, 'TITLE')
                content_shape_id = find_text_shape_id(slide, 'BODY')
            
            # Add title text (always add if title exists and shape is found)
            if title_shape_id and slide_title:
                # First, clear any existing placeholder text to prevent overlap
                # Get the shape to find current text length
                try:
                    # Get the slide page to access shape details
                    page = service.presentations().pages().get(
                        presentationId=presentation_id,
                        pageObjectId=slide.get('objectId')
                    ).execute()
                    
                    # Find the title shape and get its text length
                    current_text_length = 0
                    for element in page.get('pageElements', []):
                        if element.get('objectId') == title_shape_id:
                            shape = element.get('shape', {})
                            if shape and shape.get('text'):
                                text_content = shape.get('text', {})
                                # Get text length from text elements
                                if text_content.get('textElements'):
                                    # Calculate total length
                                    for text_elem in text_content.get('textElements', []):
                                        if 'textRun' in text_elem:
                                            current_text_length += len(text_elem['textRun'].get('content', ''))
                                    break
                    
                    # Delete existing text if any
                    if current_text_length > 0:
                        content_requests.append({
                            'deleteText': {
                                'objectId': title_shape_id,
                                'textRange': {
                                    'type': 'FIXED_RANGE',
                                    'startIndex': 0,
                                    'endIndex': current_text_length
                                }
                            }
                        })
                except Exception as e:
                    # If we can't get text length, try deleting with a large range
                    # Google Slides will handle it gracefully
                    print(f"⚠️  Could not get text length for title shape, using fallback: {e}")
                    content_requests.append({
                        'deleteText': {
                            'objectId': title_shape_id,
                            'textRange': {
                                'type': 'FIXED_RANGE',
                                'startIndex': 0,
                                'endIndex': 1000  # Large number to clear all
                            }
                        }
                    })
                
                # Limit title to max 2 lines
                limited_title = limit_title_to_lines(slide_title, max_lines=2, max_chars_per_line=60)
                
                # Parse markdown formatting
                plain_title, title_style_ranges = parse_markdown_formatting(limited_title)
                
                # Insert plain text first
                content_requests.append({
                    'insertText': {
                        'objectId': title_shape_id,
                        'insertionIndex': 0,
                        'text': plain_title
                    }
                })
                
                # Apply formatting styles
                for style_range in title_style_ranges:
                    style_updates = {}
                    if style_range.get('bold'):
                        style_updates['bold'] = True
                    if style_range.get('italic'):
                        style_updates['italic'] = True
                    
                    if style_updates:
                        content_requests.append({
                            'updateTextStyle': {
                                'objectId': title_shape_id,
                                'textRange': {
                                    'type': 'FIXED_RANGE',
                                    'startIndex': style_range['start_index'],
                                    'endIndex': style_range['end_index']
                                },
                                'style': style_updates,
                                'fields': ','.join(style_updates.keys())
                            }
                        })
                
                # Adjust title font size to be smaller (default is usually 44pt, make it 24pt)
                content_requests.append({
                    'updateTextStyle': {
                        'objectId': title_shape_id,
                        'textRange': {
                            'type': 'ALL'
                        },
                        'style': {
                            'fontSize': {
                                'magnitude': 24,
                                'unit': 'PT'
                            }
                        },
                        'fields': 'fontSize'
                    }
                })
            elif slide_title:
                print(f"⚠️  Warning: Could not find title shape for slide {slide_number}: {slide_title}")
            
            # Add body content
            if content_shape_id:
                text_content = None
                if bullet_points:
                    # Add bullet points with proper formatting
                    text_content = '\n'.join([f'• {point}' for point in bullet_points if point])
                    if main_text:
                        text_content = main_text + '\n\n' + text_content
                elif main_text:
                    text_content = main_text
                
                if text_content:
                    # Parse markdown formatting
                    plain_text, style_ranges = parse_markdown_formatting(text_content)
                    
                    # Insert plain text first
                    content_requests.append({
                        'insertText': {
                            'objectId': content_shape_id,
                            'text': plain_text
                        }
                    })
                    
                    # Apply formatting styles
                    for style_range in style_ranges:
                        style_updates = {}
                        if style_range.get('bold'):
                            style_updates['bold'] = True
                        if style_range.get('italic'):
                            style_updates['italic'] = True
                        
                        if style_updates:
                            content_requests.append({
                                'updateTextStyle': {
                                    'objectId': content_shape_id,
                                    'textRange': {
                                        'type': 'FIXED_RANGE',
                                        'startIndex': style_range['start_index'],
                                        'endIndex': style_range['end_index']
                                    },
                                    'style': style_updates,
                                    'fields': ','.join(style_updates.keys())
                                }
                            })
            elif bullet_points or main_text:
                print(f"⚠️  Warning: Could not find content shape for slide {slide_number}")
            
            # Add speaker notes from script
            script_section = script_map.get(slide_number)
            if script_section:
                # Build notes text from script
                notes_parts = []
                opening_line = script_section.get('opening_line', '')
                if opening_line:
                    notes_parts.append(opening_line)
                
                for content_item in script_section.get('main_content', []):
                    point = content_item.get('point', '')
                    explanation = content_item.get('explanation', '')
                    if point:
                        notes_parts.append(f"\n\n{point}")
                    if explanation:
                        notes_parts.append(f"\n{explanation}")
                
                notes_text = ''.join(notes_parts).strip()
                
                if notes_text:
                    # Get notes page from slide properties
                    notes_page = slide.get('slideProperties', {}).get('notesPage', {})
                    
                    if notes_page and notes_page.get('pageElements'):
                        # Find the speaker notes text box in the notes page
                        # Speaker notes are typically in a text box element
                        notes_shape_id = None
                        for element in notes_page.get('pageElements', []):
                            shape = element.get('shape', {})
                            if shape:
                                # Look for text box shapes (speaker notes container)
                                # Speaker notes text box usually has shapeType TEXT_BOX or contains text
                                shape_type = shape.get('shapeType')
                                has_text = shape.get('text', {}) and shape.get('text', {}).get('textElements')
                                
                                if shape_type == 'TEXT_BOX' or has_text:
                                    notes_shape_id = element.get('objectId')
                                    if notes_shape_id:
                                        break
                        
                        if notes_shape_id:
                            # Insert text directly (don't delete first - if there's existing text, we'll replace it)
                            # Use insertText with index 0 to insert at the beginning
                            # If we need to clear first, we'd need to check if text exists, but for simplicity,
                            # we'll just insert and let Google Slides handle it
                            content_requests.append({
                                'insertText': {
                                    'objectId': notes_shape_id,
                                    'insertionIndex': 0,
                                    'text': notes_text
                                }
                            })
                        else:
                            print(f"⚠️  Warning: Could not find speaker notes text box for slide {slide_number}")
                    else:
                        print(f"⚠️  Warning: No notes page found for slide {slide_number}")
        
        # Execute all content updates
        if content_requests:
            print(f"\n📝 Adding slide content and speaker notes ({len(content_requests)} requests)...")
            try:
                response = service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': content_requests}
                ).execute()
                print(f"✅ Successfully executed {len(content_requests)} content update requests")
                if response.get('replies'):
                    print(f"   Got {len(response.get('replies', []))} replies")
            except HttpError as e:
                print(f"❌ Error adding content: {e}")
                # Print first few requests for debugging
                print(f"   First 3 requests:")
                for i, req in enumerate(content_requests[:3]):
                    print(f"      {i}: {list(req.keys())[0]}")
                # Even if content addition fails, return the presentation info so it can still be accessed
                # The presentation was created successfully, even if content couldn't be added
                shareable_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️  Warning: Content addition failed, but presentation was created")
                logger.info(f"   🔗 Google Slides URL: {shareable_url}")
                print(f"⚠️  Warning: Content addition failed, but presentation was created: {shareable_url}")
                print(f"🔗 Google Slides URL: {shareable_url}")
                return {
                    'status': 'partial_success',
                    'presentation_id': presentation_id,
                    'shareable_url': shareable_url,
                    'message': f'Google Slides presentation created but content addition failed: {e}',
                    'error': f'Content addition error: {str(e)}'
                }
        
        # Generate shareable URL
        shareable_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"✅ Google Slides export complete!")
        logger.info(f"   Presentation ID: {presentation_id}")
        logger.info(f"   🔗 Google Slides URL: {shareable_url}")
        logger.info(f"   📝 IMPORTANT: Presentation is created in the Google account that authorized the OAuth token")
        logger.info(f"   📝 Check the Google account used when generating token.json")
        print(f"✅ Google Slides export complete!")
        print(f"   Presentation ID: {presentation_id}")
        print(f"   🔗 Google Slides URL: {shareable_url}")
        print(f"   📝 IMPORTANT: Presentation is created in the Google account that authorized the OAuth token")
        print(f"   📝 Check the Google account used when generating token.json")
        
        # Note: Browser opening is handled by the caller (main.py) via open_browser parameter
        # This allows the caller to control when/if the browser should be opened
        
        return {
            'status': 'success',
            'presentation_id': presentation_id,
            'shareable_url': shareable_url,
            'message': 'Google Slides presentation created successfully'
        }
        
    except FileNotFoundError as e:
        # Re-raise FileNotFoundError so it can be handled by the tool wrapper
        raise e
    except HttpError as error:
        print(f"❌ Google API error: {error}")
        error_details = str(error)
        # Check if presentation was created before the error
        # If so, return partial success with the presentation_id so it can still be accessed
        if presentation_id:
            shareable_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️  Warning: API error occurred, but presentation was created")
            logger.info(f"   🔗 Google Slides URL: {shareable_url}")
            print(f"⚠️  Warning: API error occurred, but presentation was created: {shareable_url}")
            print(f"🔗 Google Slides URL: {shareable_url}")
            return {
                'status': 'partial_success',
                'presentation_id': presentation_id,
                'shareable_url': shareable_url,
                'message': f'Google Slides presentation created but encountered API error: {error_details}',
                'error': error_details
            }
        # If presentation wasn't created, raise the error
        raise
    except Exception as e:
        print(f"❌ Error exporting to Google Slides: {e}")
        error_details = str(e)
        # Check if presentation was created before the error
        # If so, return partial success with the presentation_id so it can still be accessed
        if presentation_id:
            shareable_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️  Warning: Error occurred, but presentation was created")
            logger.info(f"   🔗 Google Slides URL: {shareable_url}")
            print(f"⚠️  Warning: Error occurred, but presentation was created: {shareable_url}")
            print(f"🔗 Google Slides URL: {shareable_url}")
            return {
                'status': 'partial_success',
                'presentation_id': presentation_id,
                'shareable_url': shareable_url,
                'message': f'Google Slides presentation created but encountered error: {error_details}',
                'error': error_details
            }
        # If presentation wasn't created, raise the error
        raise

