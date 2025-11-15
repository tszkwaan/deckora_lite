"""
Google Slides Exporter.
Exports slide deck and script to Google Slides using Google Slides API.
"""

import os
import json
import webbrowser
from pathlib import Path
from typing import Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes required for Google Slides API
SCOPES = ['https://www.googleapis.com/auth/presentations']

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
                    f"See SLIDESHOW_EXPORT_PLAN.md for setup instructions."
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
    try:
        # Get credentials
        creds = get_credentials()
        
        # Build service
        service = build('slides', 'v1', credentials=creds)
        
        # Create presentation
        print("📊 Creating Google Slides presentation...")
        presentation = service.presentations().create(
            body={'title': title}
        ).execute()
        presentation_id = presentation.get('presentationId')
        print(f"✅ Presentation created: {presentation_id}")
        
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
        
        # Build all requests for creating slides and adding content
        all_requests = []
        slide_object_ids = []  # Will store slide object IDs from response
        
        # First, create all slides and collect their object IDs
        for idx, slide_data in enumerate(slides):
            slide_number = slide_data.get('slide_number', idx + 1)
            
            # Determine layout
            if idx == 0:
                layout = 'TITLE'
            else:
                layout = 'TITLE_AND_BODY'
            
            # Create slide request
            all_requests.append({
                'createSlide': {
                    'slideLayoutReference': {
                        'predefinedLayout': layout
                    },
                    'insertionIndex': idx + 1
                }
            })
        
        # Execute slide creation
        if all_requests:
            print("📊 Creating slides...")
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
        
        print(f"📊 Found {len(slides_list)} slides in presentation (including default title slide)")
        
        # Now add content to each slide
        content_requests = []
        
        # Note: slides_list[0] is the default title slide that comes with new presentations
        # Our created slides start at index 1
        for idx, slide_data in enumerate(slide_deck.get('slides', [])):
            # Our slides are at index idx + 1 (skip the default title slide at index 0)
            slide_index = idx + 1
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
                title_shape_id = find_text_shape_id(slide, 'CENTERED_TITLE')
                if not title_shape_id:
                    title_shape_id = find_text_shape_id(slide, 'TITLE')
                # Title slides use SUBTITLE for content, not BODY
                content_shape_id = find_text_shape_id(slide, 'SUBTITLE')
            else:
                title_shape_id = find_text_shape_id(slide, 'TITLE')
                content_shape_id = find_text_shape_id(slide, 'BODY')
            
            # Add title text (always add if title exists and shape is found)
            if title_shape_id and slide_title:
                content_requests.append({
                    'insertText': {
                        'objectId': title_shape_id,
                        'text': slide_title
                    }
                })
                print(f"   ✅ Added title text request")
            elif slide_title:
                print(f"   ⚠️  Warning: Could not find title shape for slide {slide_number}: {slide_title}")
            
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
                    content_requests.append({
                        'insertText': {
                            'objectId': content_shape_id,
                            'text': text_content
                        }
                    })
                    print(f"   ✅ Added body content request ({len(text_content)} chars)")
                else:
                    print(f"   ⚠️  No body content to add (bullet_points={len(bullet_points)}, main_text={bool(main_text)})")
            elif bullet_points or main_text:
                print(f"   ⚠️  Warning: Could not find content shape for slide {slide_number}")
            
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
                raise
        
        # Generate shareable URL
        shareable_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        
        print(f"✅ Google Slides export complete!")
        print(f"   Presentation ID: {presentation_id}")
        print(f"   Shareable URL: {shareable_url}")
        
        # Open URL in Chrome
        try:
            print(f"\n🌐 Opening presentation in Chrome...")
            # Try to open in Chrome specifically
            chrome_path = None
            if os.name == 'nt':  # Windows
                chrome_path = 'C:/Program Files/Google/Chrome/Application/chrome.exe %s'
            elif os.name == 'posix':  # macOS/Linux
                # Try common Chrome paths on macOS
                chrome_paths = [
                    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                    '/usr/bin/google-chrome',
                    '/usr/bin/chromium-browser'
                ]
                for path in chrome_paths:
                    if os.path.exists(path):
                        chrome_path = f'"{path}" %s'
                        break
            
            if chrome_path:
                webbrowser.get(chrome_path).open(shareable_url)
            else:
                # Fall back to default browser
                webbrowser.open(shareable_url)
            print(f"✅ Opened in browser")
        except Exception as e:
            print(f"⚠️  Could not open browser automatically: {e}")
            print(f"   Please open manually: {shareable_url}")
        
        return {
            'status': 'success',
            'presentation_id': presentation_id,
            'shareable_url': shareable_url,
            'message': 'Google Slides presentation created successfully'
        }
        
    except FileNotFoundError as e:
        raise e
    except HttpError as error:
        print(f"❌ Google API error: {error}")
        raise
    except Exception as e:
        print(f"❌ Error exporting to Google Slides: {e}")
        raise

