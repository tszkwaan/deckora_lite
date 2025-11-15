# Slideshow Export Implementation Plan

## 🎯 **DECISION: Google Slides API** ⭐

**Why Google Slides:**
- ✅ Perfect for Google x Kaggle competition - uses Google's own tools!
- ✅ Cloud-based, accessible anywhere
- ✅ Easy sharing and collaboration
- ✅ Supports speaker notes
- ✅ Professional and impressive for competition
- ✅ Integrates with Google Workspace ecosystem
- ✅ Can export to PDF/PPTX later if needed

---

## 1. Format: Google Slides (via API)

### Advantages:
- **Competition Alignment**: Perfect for Google x Kaggle - demonstrates use of Google tools
- **Cloud-based**: Accessible from any device
- **Collaborative**: Multiple users can edit simultaneously
- **Easy Sharing**: Share via link, no file downloads needed
- **Speaker Notes**: Full support for speaker notes from script
- **Professional**: Industry-standard format
- **Integration**: Works seamlessly with other Google services

### Implementation:
- Use **Google Slides API** (v1)
- Authenticate using Google OAuth2 or Service Account
- Create presentation programmatically
- Add slides with content from JSON
- Include speaker notes from script

---

## 2. Recommended Approach: Google Slides API

### Phase 1: Google Slides API Setup
**Why:** Perfect for Google x Kaggle competition

**Setup Steps:**
1. **Enable Google Slides API** in Google Cloud Console
2. **Create OAuth2 credentials** (for user authentication)
   - Or use Service Account (for automated access)
3. **Install Google API libraries**
4. **Authenticate and get credentials**

**Libraries Required:**
- `google-api-python-client` - Google API client
- `google-auth-httplib2` - HTTP transport
- `google-auth-oauthlib` - OAuth2 authentication

---

### Phase 2: Google Slides Export Implementation
**Why:** Generate presentation programmatically

**Implementation Steps:**
1. Create `utils/google_slides_exporter.py`
2. Use Google Slides API to:
   - Create new presentation
   - Add slides with layouts (TITLE, TITLE_AND_BODY, etc.)
   - Insert text content (titles, bullet points, main text)
   - Add speaker notes from script
   - Apply basic formatting
3. Map JSON structure to Google Slides:
   - `slide_deck.slides[]` → Google Slides
   - `slide.title` → Slide title shape
   - `slide.content.bullet_points[]` → Bulleted list
   - `slide.content.main_text` → Body text
   - `presentation_script.script_sections[].main_content[].explanation` → Speaker notes

**Output:** Google Slides presentation (shared via link or file ID)

**API Methods:**
- `presentations().create()` - Create new presentation
- `presentations().batchUpdate()` - Add slides and content
- `presentations().get()` - Retrieve presentation

---

## 3. Implementation Details

### Data Mapping

**From `slide_deck.json`:**
```json
{
  "slides": [
    {
      "slide_number": 1,
      "title": "...",
      "content": {
        "main_text": "...",
        "bullet_points": [...],
        "subheadings": [...]
      },
      "visual_elements": {
        "figures": [...],
        "charts_needed": false,
        "icons_suggested": [...]
      },
      "formatting_notes": "...",
      "speaker_notes": "..."
    }
  ]
}
```

**From `presentation_script.json`:**
```json
{
  "script_sections": [
    {
      "slide_number": 1,
      "slide_title": "...",
      "main_content": [
        {
          "point": "...",
          "explanation": "...",
          "estimated_time": 30
        }
      ],
      "transitions": {...}
    }
  ]
}
```

**To Google Slides:**
- Slide title → Title shape (text box)
- Bullet points → Body shape with bullet formatting
- Main text → Body shape (paragraph text)
- Speaker notes → Notes page (speaker notes)
- Script explanations → Enhanced speaker notes
- Transitions → Slide transition properties

---

### File Structure

```
utils/
  └── google_slides_exporter.py    # Google Slides API exporter

credentials/
  └── credentials.json              # OAuth2 credentials (gitignored)
  └── token.json                    # OAuth2 token (gitignored)

output/
  └── presentation_slides_id.txt   # Google Slides presentation ID
  └── presentation_slides_url.txt  # Shareable URL
```

---

### Code Structure

```python
# utils/google_slides_exporter.py

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/presentations']

def get_credentials():
    """Get OAuth2 credentials for Google Slides API."""
    # Load credentials from credentials.json
    # Handle token refresh
    pass

def export_to_google_slides(
    slide_deck: dict,
    presentation_script: dict,
    config: PresentationConfig,
    title: str = "Generated Presentation"
) -> dict:
    """
    Export slide deck and script to Google Slides.
    
    Args:
        slide_deck: Slide deck JSON from slide generator
        presentation_script: Script JSON from script generator
        config: Presentation configuration
        title: Presentation title
        
    Returns:
        Dict with presentation_id and shareable_url
    """
    # 1. Authenticate and build service
    creds = get_credentials()
    service = build('slides', 'v1', credentials=creds)
    
    # 2. Create presentation
    presentation = service.presentations().create(
        body={'title': title}
    ).execute()
    presentation_id = presentation.get('presentationId')
    
    # 3. Build batch update requests
    requests = []
    
    # 4. For each slide in slide_deck:
    for slide_data in slide_deck['slides']:
        # Create slide with layout
        requests.append({
            'createSlide': {
                'slideLayoutReference': {
                    'predefinedLayout': 'TITLE_AND_BODY'  # or 'TITLE' for title slide
                }
            }
        })
        
        # Add title text
        # Add body text (bullets or main text)
        # Add speaker notes from script
        
    # 5. Execute batch update
    service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={'requests': requests}
    ).execute()
    
    # 6. Get shareable URL
    shareable_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    
    return {
        'presentation_id': presentation_id,
        'shareable_url': shareable_url
    }
```

---

## 4. Dependencies

**Required:**
```txt
google-api-python-client>=2.0.0    # Google API client
google-auth-httplib2>=0.1.0        # HTTP transport
google-auth-oauthlib>=1.0.0        # OAuth2 authentication
```

**Setup:**
1. Enable Google Slides API in [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth2 credentials (Desktop app)
3. Download `credentials.json` to `credentials/` folder
4. First run will open browser for authentication
5. Token will be saved to `credentials/token.json`

---

## 5. Integration with Pipeline

**In `main.py`:**
```python
# After script generation
if script and slide_deck:
    from utils.google_slides_exporter import export_to_google_slides
    
    print("\n" + "=" * 60)
    print("📊 Exporting to Google Slides...")
    print("=" * 60)
    
    result = export_to_google_slides(
        slide_deck=slide_deck,
        presentation_script=script,
        config=config,
        title=f"Presentation: {config.scenario}"
    )
    
    print(f"✅ Google Slides created!")
    print(f"   Presentation ID: {result['presentation_id']}")
    print(f"   Shareable URL: {result['shareable_url']}")
    
    # Save IDs to file
    with open(f"{output_dir}/presentation_slides_id.txt", "w") as f:
        f.write(result['presentation_id'])
    with open(f"{output_dir}/presentation_slides_url.txt", "w") as f:
        f.write(result['shareable_url'])
```

---

## 6. Features to Implement

### Basic (MVP):
- [x] Title slide
- [x] Content slides with titles
- [x] Bullet points
- [x] Main text content
- [x] Speaker notes from script

### Enhanced (Future):
- [ ] Custom layouts based on slide type
- [ ] Apply theme/colors from design_style_config
- [ ] Add placeholder for figures/images
- [ ] Formatting based on formatting_notes
- [ ] Charts/tables if needed
- [ ] Slide transitions
- [ ] HTML export option

---

## 7. Recommendations

**Start with Google Slides API:**
1. ✅ Perfect for Google x Kaggle competition
2. ✅ Demonstrates use of Google's tools
3. ✅ Cloud-based, accessible anywhere
4. ✅ Supports speaker notes (critical for our use case)
5. ✅ Easy sharing and collaboration
6. ✅ Can export to PDF/PPTX later if needed

**Implementation Priority:**
1. ✅ Set up Google Slides API authentication
2. ✅ Basic Google Slides export (titles, bullets, notes)
3. ⏳ Enhanced formatting and layouts
4. ⏳ Speaker notes integration
5. ⏳ Share settings and permissions

---

## 8. Example Output Structure

```
output/
├── report_knowledge.json
├── presentation_outline.json
├── outline_review.json
├── slide_deck.json
├── presentation_script.json
├── quality_logs.json
├── complete_output.json
├── presentation_slides_id.txt    ← NEW (Google Slides ID)
└── presentation_slides_url.txt    ← NEW (Shareable URL)

credentials/  (gitignored)
├── credentials.json               ← OAuth2 credentials
└── token.json                     ← OAuth2 token
```

---

## 9. Google Slides API Setup Guide

### Step 1: Enable Google Slides API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable "Google Slides API"
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Choose "Desktop app"
6. Download credentials as `credentials.json`

### Step 2: Install Dependencies
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Step 3: First Run Authentication
- First run will open browser for OAuth2 authentication
- Grant permissions to access Google Slides
- Token saved to `credentials/token.json` for future use

### Step 4: API Usage
- Use `presentations().create()` to create new presentation
- Use `presentations().batchUpdate()` to add slides and content
- Use `presentations().get()` to retrieve presentation details

---

## Next Steps

1. **Add Google API libraries to requirements.txt**
2. **Set up Google Cloud project and enable Slides API**
3. **Create `utils/google_slides_exporter.py`**
4. **Implement authentication flow**
5. **Implement basic Google Slides export (titles, bullets, notes)**
6. **Integrate into main.py pipeline**
7. **Test with existing slide_deck.json and presentation_script.json**
8. **Add speaker notes from script**
9. **Enhance formatting and layouts**

