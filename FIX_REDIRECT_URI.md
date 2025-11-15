# Fix: redirect_uri_mismatch Error

## The Problem

If you're seeing this error:
```
Error 400: redirect_uri_mismatch
Access blocked: This app's request is invalid
```

**Most likely cause**: You created a "Web application" OAuth client instead of a "Desktop app" client!

## Solution: Create Desktop App Client

1. **Go to Google Cloud Console**:
   - Navigate to: https://console.cloud.google.com/
   - Select your project
   - Go to "APIs & Services" → "Credentials"

2. **Delete the wrong client** (if you created a "Web application"):
   - Find your "Web client" or "Web application" OAuth client
   - Click on it and click "Delete" (or just create a new one)

3. **Create a NEW OAuth Client**:
   - Click "Create Credentials" → "OAuth client ID"
   - **Application type: "Desktop app"** ⚠️ (NOT "Web application")
   - Name: "Deckora Lite Desktop Client"
   - Click "Create"
   - **Note**: Desktop apps don't show "Authorized redirect URIs" - that's normal!

4. **Download the NEW credentials**:
   - Click the download icon (⬇️) next to your NEW Desktop app client
   - Save as `credentials.json`
   - Replace your old `credentials/credentials.json` with the new one

5. **Try again**:
   - Delete `credentials/token.json` if it exists:
     ```bash
     rm credentials/token.json
     ```
   - Run your script again:
     ```bash
     python test_google_slides_exporter.py
     ```

## How to Tell the Difference

- **Desktop app**: No "Authorized redirect URIs" field, uses `InstalledAppFlow`
- **Web application**: Has "Authorized JavaScript origins" and "Authorized redirect URIs" fields

## Why This Happens

Our code uses `InstalledAppFlow.run_local_server()` which is designed for desktop applications. This flow automatically handles redirect URIs and doesn't require manual configuration.

Web application clients use a different OAuth flow that requires explicit redirect URI configuration, which won't work with our desktop app code.

