# Gemini Vision - How It Works

## Overview

Gemini Vision is a **multimodal AI model** that can process both **text and images** together. It's part of Google's Gemini family of models.

## What Inputs Does Gemini Vision Accept?

### ❌ **NOT Direct URLs**
Gemini Vision **cannot** directly accept a Google Slides URL. You need to provide the **actual image data**.

### ✅ **Accepted Input Formats:**

1. **Image File Path** (local file)
   ```python
   image_path = "/path/to/slide.png"
   ```

2. **Image Bytes** (in-memory image data)
   ```python
   with open("slide.png", "rb") as f:
       image_bytes = f.read()
   ```

3. **Base64 Encoded Image**
   ```python
   import base64
   with open("slide.png", "rb") as f:
       image_base64 = base64.b64encode(f.read()).decode()
   ```

4. **PIL Image Object** (Python Imaging Library)
   ```python
   from PIL import Image
   image = Image.open("slide.png")
   ```

5. **NumPy Array** (image as array)
   ```python
   import numpy as np
   image_array = np.array(image)
   ```

## How Gemini Vision Works

### Basic Flow:

```
1. You provide: Image data + Text prompt
2. Gemini processes: Both image and text together
3. Gemini returns: Text response analyzing the image
```

### Example:

```python
# Input
Image: [slide screenshot]
Prompt: "Check this slide for text overlap and layout issues"

# Output
{
  "overlaps_detected": true,
  "issues": [
    "Title text overlaps with body content on slide 3",
    "Font size too small on slide 5"
  ]
}
```

## Using Gemini Vision with Google ADK

Since you're using **Google ADK** (Agent Development Kit), here's how to use Gemini Vision:

### Option 1: Using Gemini Model Directly (Not via ADK)

```python
from google.genai import Client
import base64

# Initialize client
client = Client(api_key="your-api-key")

# Load image
with open("slide.png", "rb") as f:
    image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode()

# Create content with image
response = client.models.generate_content(
    model="gemini-2.5-pro-vision",  # Vision-capable model
    contents=[
        {
            "role": "user",
            "parts": [
                {"text": "Review this slide for layout issues:"},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_base64
                    }
                }
            ]
        }
    ]
)

print(response.text)
```

### Option 2: Using ADK with Multimodal Input

```python
from google.adk.models.google_llm import Gemini
from google.adk.agents import LlmAgent
from PIL import Image
import io

# Create vision-capable model
vision_model = Gemini(
    model="gemini-2.5-pro-vision",  # Note: vision model
    retry_options=RETRY_CONFIG,
)

# Load image
image = Image.open("slide.png")

# Convert to bytes
img_bytes = io.BytesIO()
image.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Create agent that can handle images
agent = LlmAgent(
    name="LayoutCriticAgent",
    model=vision_model,
    instruction="You are a layout critic. Analyze slides for layout issues.",
    tools=[],
)

# Send message with image
# Note: ADK may need special handling for multimodal input
# Check ADK documentation for exact format
```

## For Your Use Case: Reviewing Google Slides

### Step-by-Step Process:

```python
def review_slide_with_gemini_vision(slide_image_path: str) -> dict:
    """
    Review a slide image using Gemini Vision.
    
    Steps:
    1. Load slide image (from screenshot or export)
    2. Pass image + prompt to Gemini Vision
    3. Get analysis results
    """
    from google.genai import Client
    import base64
    
    # Step 1: Load image
    with open(slide_image_path, "rb") as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode()
    
    # Step 2: Create prompt
    prompt = """
    Review this presentation slide for layout issues:
    
    1. Check for text overlap - are any text elements visually overlapping?
    2. Check spacing - is there adequate whitespace between elements?
    3. Check text overflow - does any text extend beyond its container?
    4. Check font sizes - are they appropriate and readable?
    5. Check alignment - are elements properly aligned?
    
    Note: Consider that text boxes may have padding/margins, so bounding boxes 
    might overlap even if actual text doesn't. Focus on VISUAL overlap of text content.
    
    Return JSON with:
    {
        "overlaps_detected": true/false,
        "issues": ["issue1", "issue2"],
        "recommendations": ["rec1", "rec2"]
    }
    """
    
    # Step 3: Call Gemini Vision API
    client = Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    response = client.models.generate_content(
        model="gemini-2.5-pro-vision",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_base64
                        }
                    }
                ]
            }
        ]
    )
    
    # Step 4: Parse response
    result = json.loads(response.text)
    return result
```

## Getting Slide Images

Since Gemini Vision needs **image data**, not URLs, you need to:

### Option A: Screenshot (Selenium)
```python
from selenium import webdriver
from PIL import Image

def capture_slide_screenshot(presentation_url: str, slide_num: int) -> Image:
    driver = webdriver.Chrome()
    driver.get(f"{presentation_url}#slide=id.{slide_num}")
    screenshot = driver.save_screenshot("slide.png")
    return Image.open("slide.png")
```

### Option B: Export as PDF then Convert
```python
from pdf2image import convert_from_bytes
from googleapiclient.discovery import build

def get_slide_images(presentation_id: str) -> list:
    # Export as PDF
    drive_service = build('drive', 'v3', credentials=creds)
    pdf_data = drive_service.files().export_media(
        fileId=presentation_id,
        mimeType='application/pdf'
    ).execute()
    
    # Convert PDF pages to images
    images = convert_from_bytes(pdf_data)
    return images  # List of PIL Images
```

## Complete Example: Review All Slides

```python
def review_all_slides_vision(presentation_id: str) -> dict:
    """
    Review all slides using Gemini Vision.
    """
    # Step 1: Get slide images
    slide_images = get_slide_images(presentation_id)
    
    # Step 2: Review each slide
    all_issues = []
    for slide_num, image in enumerate(slide_images, start=1):
        # Save image temporarily
        image_path = f"/tmp/slide_{slide_num}.png"
        image.save(image_path)
        
        # Review with Gemini Vision
        review = review_slide_with_gemini_vision(image_path)
        
        if review.get("overlaps_detected") or review.get("issues"):
            all_issues.append({
                "slide_number": slide_num,
                "issues": review.get("issues", []),
                "recommendations": review.get("recommendations", [])
            })
        
        # Clean up
        os.remove(image_path)
    
    return {
        "total_slides": len(slide_images),
        "issues_found": len(all_issues),
        "issues": all_issues
    }
```

## Key Points

1. **Gemini Vision needs image DATA, not URLs**
   - You must provide the actual image file/bytes
   - Cannot directly pass Google Slides URL

2. **Model name matters**
   - Use `gemini-2.5-pro-vision` or `gemini-2.0-flash-exp-vision`
   - Regular `gemini-2.5-pro` may not support vision

3. **Input format**
   - Base64 encoded image data
   - Or file path (depending on API)
   - MIME type must be specified (image/png, image/jpeg)

4. **Multimodal input**
   - Can combine text prompt + image
   - Gemini understands context between text and image

5. **Output**
   - Returns text response (can be JSON)
   - Can analyze visual layout, detect overlaps, assess aesthetics

## Comparison: URL vs Image Data

| Input Type | Works? | Why |
|------------|--------|-----|
| Google Slides URL | ❌ No | Gemini Vision doesn't fetch URLs |
| Image file path | ✅ Yes | Direct file access |
| Image bytes/base64 | ✅ Yes | In-memory image data |
| Screenshot | ✅ Yes | Captured image data |
| PDF export → images | ✅ Yes | Converted to image format |

## Summary

**To use Gemini Vision for reviewing Google Slides:**

1. **Export/capture slides as images** (PNG/JPEG)
2. **Load image data** (file path or bytes)
3. **Pass image + prompt to Gemini Vision**
4. **Get analysis results** (text/JSON response)

The model "sees" the image just like a human would, making it excellent for detecting visual layout issues!

