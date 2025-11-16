# Layout Review Setup Guide

The layout critic agent uses Google Cloud Vision API to analyze Google Slides for layout issues like text overlap and overflow.

## Prerequisites

1. **Google Slides API** - Already set up (uses same credentials)
2. **Google Cloud Vision API** - Needs to be enabled

## Step 1: Enable Vision API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (same one used for Slides API)
3. Go to "APIs & Services" → "Library"
4. Search for "Cloud Vision API"
5. Click "Enable"

## Step 2: Credentials

The layout review tool will try to use the same OAuth credentials as Google Slides API. If that doesn't work, you can:

### Option A: Use Same OAuth Credentials (Recommended)
- The tool will automatically use your existing `credentials/token.json`
- No additional setup needed if Slides API is working

### Option B: Use Service Account (For Production)
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Download the JSON key file
4. Set environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   ```

### Option C: Use gcloud CLI
```bash
gcloud auth application-default login
```

## Step 3: Install Dependencies

```bash
pip install google-cloud-vision pdf2image Pillow
```

**Note:** `pdf2image` requires `poppler`:
- **macOS**: `brew install poppler`
- **Linux**: `sudo apt-get install poppler-utils`
- **Windows**: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases)

## Step 4: Test

The layout review will automatically run after Google Slides export. It will:
1. Export slides as PDF
2. Convert PDF pages to images
3. Analyze each image with Vision API
4. Detect text overlaps and overflow issues
5. Generate a layout review report

## Output

The layout review is saved to:
- `output/layout_review.json` - Detailed review with issues and recommendations

## Troubleshooting

### Error: "Vision API credentials not found"
- Make sure Vision API is enabled in Google Cloud Console
- Try Option B or C above for credentials

### Error: "poppler not found"
- Install poppler (see Step 3)
- Make sure it's in your PATH

### Error: "PDF conversion failed"
- Check that poppler is installed correctly
- Try reducing DPI in `export_slides_as_images()` (currently 200)

## Cost

- **Vision API**: First 1,000 requests/month are free
- **PDF Export**: Free (uses Drive API)
- **Image Conversion**: Free (local processing)

For a 20-slide presentation, that's ~20 Vision API calls per review.

