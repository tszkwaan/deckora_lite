# Setting Up GOOGLE_TOKEN_JSON GitHub Secret

## Quick Answer

**Yes, you should paste the entire contents of `token.json` into the GitHub Secret `GOOGLE_TOKEN_JSON`.**

## Steps

### 1. Get Your `token.json` Content

**Option A: From Local File**
```bash
cat presentation_agent/agents/credentials/token.json
```

**Option B: Copy from IDE**
- Open `presentation_agent/agents/credentials/token.json`
- Select all content (Cmd+A / Ctrl+A)
- Copy (Cmd+C / Ctrl+C)

### 2. Add to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to: **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Fill in:
   - **Name**: `GOOGLE_TOKEN_JSON`
   - **Value**: Paste the **entire JSON content** from `token.json`
5. Click **"Add secret"**

### 3. Verify Format

The secret should contain a **valid JSON object** like this:

```json
{
  "token": "ya29.a0ATi6K2v...",
  "refresh_token": "1//0g2SryLx...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "...",
  "client_secret": "...",
  "scopes": ["https://www.googleapis.com/auth/presentations", ...],
  "universe_domain": "googleapis.com",
  "account": "",
  "expiry": "2025-11-21T17:28:09.483373Z"
}
```

**Important:**
- ✅ Paste the **entire JSON object** (including all fields)
- ✅ Ensure it's **valid JSON** (no trailing commas, proper quotes)
- ✅ **No extra whitespace** at the beginning/end (GitHub Secrets will trim it)
- ✅ The workflow will validate it during build

### 4. How It Works

The GitHub Actions workflow (`.github/workflows/deploy.yml`) will:

1. Read `GOOGLE_TOKEN_JSON` from GitHub Secrets
2. Parse it as JSON (validates format)
3. Write it to `presentation_agent/agents/credentials/token.json` in the Docker image
4. The application will use this file for OAuth authentication

### 5. Troubleshooting

**If you get "token.json is not valid JSON" error:**

1. **Check for extra characters:**
   - Make sure you copied the entire JSON object
   - No extra text before/after the JSON
   - No markdown code blocks (```json ... ```)

2. **Validate locally:**
   ```bash
   python3 -c "import json; json.load(open('presentation_agent/agents/credentials/token.json'))"
   ```

3. **Common issues:**
   - ❌ Copying only part of the JSON
   - ❌ Including file path or comments
   - ❌ Extra whitespace or newlines
   - ✅ **Correct:** Just the raw JSON object

### 6. Security Notes

- ⚠️ **Never commit `token.json` to git** (it's in `.gitignore`)
- ✅ **GitHub Secrets are encrypted** and only accessible during workflow runs
- ✅ **Token expires** - you may need to regenerate it if it expires
- ✅ **Refresh token** allows automatic token renewal

### 7. Token Expiry

If your token expires:
1. The `refresh_token` should allow automatic renewal
2. If refresh fails, you'll need to:
   - Run OAuth flow locally again
   - Get new `token.json`
   - Update `GOOGLE_TOKEN_JSON` secret with new content

---

## Summary

**Yes, paste the entire `token.json` content into `GOOGLE_TOKEN_JSON` GitHub Secret.**

The workflow expects a **valid JSON string** that will be parsed and written to the file during Docker build.

