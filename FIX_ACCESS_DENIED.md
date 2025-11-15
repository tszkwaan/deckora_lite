# Fix: Error 403: access_denied

## The Problem

If you're seeing this error:
```
Error 403: access_denied
Deckora Lite has not completed the Google verification process
The app is currently being tested, and can only be accessed by developer-approved test users.
```

**This means**: Your OAuth consent screen is in "Testing" mode and you haven't added yourself as a test user.

## Solution: Add Yourself as a Test User

**You don't need to wait for Google verification!** For personal use, just add yourself as a test user.

### Steps:

1. **Go to OAuth Consent Screen**:
   - Navigate to: https://console.cloud.google.com/
   - Select your project
   - Go to "APIs & Services" → "OAuth consent screen"

2. **Go to Test Users Section**:
   - Scroll down to **"Test users"** (Step 4 in the setup)
   - Or click on the "Test users" tab if you're editing

3. **Add Your Email**:
   - Click **"Add Users"** button
   - Enter your Google account email: `tszkwan.chongtk@gmail.com` (or your email)
   - Click **"Add"**
   - Your email should appear in the test users list

4. **Save**:
   - Click **"Save"** at the bottom

5. **Try Again**:
   - Delete `credentials/token.json`:
     ```bash
     rm credentials/token.json
     ```
   - Run your script again:
     ```bash
     python test_google_slides_exporter.py
     ```

## Why This Happens

When you create an OAuth consent screen as "External", Google puts it in "Testing" mode by default. In testing mode, only users explicitly added as "Test users" can access the app.

For personal use, you don't need to:
- ✅ Wait for Google verification
- ✅ Submit for review
- ✅ Publish the app

Just add yourself as a test user and you're good to go!

## Alternative: Publish the App (Not Recommended for Personal Use)

If you want anyone to use it (not just test users), you can:
1. Go to OAuth consent screen
2. Click "Publish App"
3. But this requires verification if you use sensitive scopes

**For personal use, just add yourself as a test user - it's much simpler!**

