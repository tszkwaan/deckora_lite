# Fix: Insufficient Authentication Scopes

## Problem
The layout review tool needs `drive.readonly` scope to export Google Slides as PDF, but your existing token only has `presentations` scope.

## Solution

### Step 1: Delete the old token
```bash
rm credentials/token.json
```

### Step 2: Re-run the pipeline
When you run `main.py` again, it will:
1. Detect that no token exists
2. Open a browser for OAuth authentication
3. Request both scopes:
   - `https://www.googleapis.com/auth/presentations` (for creating/editing slides)
   - `https://www.googleapis.com/auth/drive.readonly` (for exporting PDFs)
4. Save the new token with both scopes

### Step 3: Verify
After re-authentication, the layout review should work without the "insufficient authentication scopes" error.

## What Changed
- Updated `utils/google_slides_exporter.py` to request `drive.readonly` scope
- This ensures both the exporter and layout review tools can use the same token
- Both tools now share the same scopes for consistency

