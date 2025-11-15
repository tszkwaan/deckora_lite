# Google Slides API Setup Guide

This guide will help you set up Google Slides API access for exporting presentations.

## Step 1: Enable Google Slides API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Create a new project** (or select an existing one):
   - Click on the project dropdown at the top
   - Click "New Project"
   - Enter project name (e.g., "Deckora Lite")
   - Click "Create"

3. **Enable Google Slides API**:
   - In the project, go to "APIs & Services" → "Library"
   - Search for "Google Slides API"
   - Click on it and click "Enable"

## Step 2: Create OAuth2 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" (unless you have a Google Workspace account)
   - Fill in required fields:
     - App name: "Deckora Lite"
     - User support email: Your email
     - Developer contact: Your email
   - Click "Save and Continue"
   - **Step 3: Scopes (optional)** - Click "Add or remove scopes":
     - In the filter/search box, type: `presentations`
     - Find and select: **`https://www.googleapis.com/auth/presentations`**
       - Description: "See, edit, create, and delete all your Google Slides presentations"
     - Click "Update" or "Add to table"
     - Click "Save and Continue"
   - **Step 4: Test users** (CRITICAL for personal use):
     - Click "Add Users"
     - Add your Google account email: `tszkwan.chongtk@gmail.com` (or your email)
     - Click "Add"
     - **Important**: Only test users can use the app until it's verified
     - For personal use, just add yourself as a test user
     - Click "Save and Continue"

4. **Create OAuth Client ID**:
   - **CRITICAL**: Application type must be **"Desktop app"** (NOT "Web application")
   - Name: "Deckora Lite Desktop Client"
   - **Important**: Desktop apps don't have "Authorized redirect URIs" field - they use a different OAuth flow
   - Click "Create"
   - **Note**: If you see "Authorized redirect URIs" field, you're creating a Web application - go back and select "Desktop app" instead

5. **Download credentials**:
   - Click the download icon (⬇️) next to your OAuth client
   - Save the file as `credentials.json`
   - Move it to the `credentials/` folder in your project:
     ```bash
     mkdir -p credentials
     mv ~/Downloads/credentials.json credentials/
     ```

## Step 3: Install Dependencies

```bash
python -m pip install -r requirements.txt
```

This will install:
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`

## Step 4: First Run Authentication

When you run the pipeline for the first time with Google Slides export:

1. The script will open your default web browser
2. Sign in with your Google account
3. Grant permissions to access Google Slides
4. The authentication token will be saved to `credentials/token.json`
5. Future runs will use this token automatically

## Step 5: Verify Setup

Run the pipeline:

```bash
python main.py
```

If everything is set up correctly, you should see:
```
📊 Exporting to Google Slides...
✅ Presentation created: [presentation_id]
📝 Adding X slides...
✅ Google Slides export complete!
   Presentation ID: [id]
   Shareable URL: [url]
```

## Troubleshooting

### Error: "Credentials file not found"
- Make sure `credentials.json` is in the `credentials/` folder
- Check the file path is correct

### Error: "Access denied" or "Permission denied"
- Make sure you've enabled Google Slides API
- Check that you've granted the correct scopes
- Try deleting `credentials/token.json` and re-authenticating

### Error: "redirect_uri_mismatch" or "Error 400: redirect_uri_mismatch"
- **This usually means you created a "Web application" instead of "Desktop app"!**
- **Solution**: Create a NEW OAuth client with the correct type:
  1. Go to Google Cloud Console → "APIs & Services" → "Credentials"
  2. Click "Create Credentials" → "OAuth client ID"
  3. **Application type: "Desktop app"** (NOT "Web application")
  4. Name: "Deckora Lite Desktop Client"
  5. Click "Create"
  6. Download the NEW credentials.json
  7. Replace your old credentials.json with the new one
  8. Delete `credentials/token.json` and try again
- **Why**: Desktop apps use `InstalledAppFlow` which handles redirect URIs automatically. Web applications require manual redirect URI configuration and won't work with our code.

### Error: "Invalid credentials"
- Delete `credentials/token.json` and re-authenticate
- Make sure your OAuth client is set up correctly

### Error: "Error 403: access_denied" or "has not completed the Google verification process"
- **This means you haven't added yourself as a test user!**
- **Solution**: Add yourself as a test user:
  1. Go to Google Cloud Console → "APIs & Services" → "OAuth consent screen"
  2. Scroll down to "Test users" section (Step 4)
  3. Click "Add Users"
  4. Add your Google account email (the one you're signing in with)
  5. Click "Add"
  6. Click "Save"
  7. Delete `credentials/token.json` and try again
- **Note**: For personal use, you don't need to verify the app - just add yourself as a test user

### Browser doesn't open
- Make sure you're running in an environment with a browser
- For headless servers, you may need to use a service account instead

## File Structure

After setup, your project should have:

```
deckora-lite/
├── credentials/
│   ├── credentials.json    ← OAuth2 credentials (from Google Cloud)
│   └── token.json          ← Auto-generated on first run
├── utils/
│   └── google_slides_exporter.py
└── ...
```

**Important**: Both `credentials.json` and `token.json` are in `.gitignore` and should NOT be committed to git.

## Next Steps

Once set up, the Google Slides export will automatically run after script generation. The presentation will be:
- Created in your Google Drive
- Accessible via the shareable URL
- Include all slides with content and speaker notes

