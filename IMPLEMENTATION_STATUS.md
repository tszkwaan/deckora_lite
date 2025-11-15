# Google Slides Export - Implementation Status

## ✅ What's Been Implemented

1. **Dependencies Added**
   - `google-api-python-client>=2.0.0`
   - `google-auth-httplib2>=0.1.0`
   - `google-auth-oauthlib>=1.0.0`
   - Added to `requirements.txt`

2. **Google Slides Exporter Module**
   - Created `utils/google_slides_exporter.py`
   - Implements OAuth2 authentication flow
   - Creates Google Slides presentations
   - Adds slides with titles and content
   - Maps slide_deck.json to Google Slides format
   - Handles bullet points and main text

3. **Pipeline Integration**
   - Integrated into `main.py` after script generation
   - Automatically exports to Google Slides if slide_deck and script are available
   - Saves presentation ID and URL to output files
   - Gracefully handles errors (continues if Google Slides setup incomplete)

4. **Documentation**
   - Created `GOOGLE_SLIDES_SETUP.md` with detailed setup instructions
   - Updated `SLIDESHOW_EXPORT_PLAN.md` with Google Slides focus
   - Added credentials to `.gitignore`

## 🔧 What You Need to Do

### Step 1: Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### Step 2: Set Up Google Cloud Project

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Create a new project** (or use existing)
3. **Enable Google Slides API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Slides API"
   - Click "Enable"

### Step 3: Create OAuth2 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Configure OAuth consent screen (if first time):
   - Choose "External"
   - Fill in app name: "Deckora Lite"
   - Add your email
   - Add scope: `https://www.googleapis.com/auth/presentations`
4. Create OAuth Client:
   - Application type: **"Desktop app"**
   - Name: "Deckora Lite Desktop Client"
5. **Download credentials.json**:
   - Click download icon
   - Save to: `credentials/credentials.json`

### Step 4: First Run

1. Run the pipeline:
   ```bash
   python main.py
   ```

2. On first run with Google Slides export:
   - Browser will open automatically
   - Sign in with your Google account
   - Grant permissions
   - Token saved to `credentials/token.json`

3. Future runs will use saved token automatically.

## 📋 Expected Output

After successful setup, you'll see:
```
📊 Exporting to Google Slides...
✅ Presentation created: [presentation_id]
📝 Adding 12 slides...
📝 Adding slide content...
✅ Google Slides export complete!
   Presentation ID: [id]
   Shareable URL: https://docs.google.com/presentation/d/[id]/edit
```

Files created:
- `output/presentation_slides_id.txt` - Presentation ID
- `output/presentation_slides_url.txt` - Shareable URL

## 🐛 Troubleshooting

### "Credentials file not found"
- Make sure `credentials.json` is in `credentials/` folder
- Check file name is exactly `credentials.json`

### "Access denied"
- Verify Google Slides API is enabled
- Check OAuth consent screen is configured
- Delete `credentials/token.json` and re-authenticate

### Browser doesn't open
- Make sure you're running in a GUI environment
- For servers, consider using service account instead

## 📝 Notes

- Speaker notes implementation is basic - may need refinement
- First slide uses TITLE layout, others use TITLE_AND_BODY
- Bullet points are formatted with "•" prefix
- All credentials are gitignored for security

## 🚀 Next Steps

1. Complete Google Cloud setup (Steps 1-3 above)
2. Run the pipeline to test
3. Check the generated Google Slides presentation
4. If notes don't work, we can refine that in a follow-up

