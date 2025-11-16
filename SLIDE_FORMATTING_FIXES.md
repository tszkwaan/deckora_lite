# Slide Formatting Fixes - Implementation Plan

## Issues Identified

1. **Bold formatting not applied**: Markdown-style `**text**` appears as literal text instead of bold
2. **Text overlap**: Text overlaps on slides, making content unreadable

---

## Issue 1: Bold Formatting (`**text**` not applied)

### Problem
The slide content contains markdown-style formatting (e.g., `**Session A:**`, `**Models Tested:**`), but the current implementation uses `insertText` which only inserts plain text. Google Slides API requires separate `updateTextStyle` requests to apply formatting.

### Current Code Location
`utils/google_slides_exporter.py` lines 260-287

### Suggested Solution

**Step 1: Create a text formatting parser function**
```python
def parse_markdown_formatting(text: str) -> tuple[str, list[dict]]:
    """
    Parse markdown-style formatting and return plain text with style ranges.
    
    Args:
        text: Text with markdown formatting (e.g., "**bold**", "*italic*")
        
    Returns:
        Tuple of (plain_text, style_ranges)
        style_ranges: List of dicts with format:
            {
                'start_index': int,
                'end_index': int,
                'bold': bool,
                'italic': bool
            }
    """
    # Parse **text** for bold
    # Parse *text* for italic (but not **text**)
    # Track positions and build style ranges
    pass
```

**Step 2: Modify text insertion to use two-phase approach**
1. First, insert plain text (with markdown markers removed)
2. Then, apply `updateTextStyle` requests for each formatted range

**Step 3: Update the content insertion logic**
```python
# Instead of:
content_requests.append({
    'insertText': {
        'objectId': content_shape_id,
        'text': text_content
    }
})

# Do:
plain_text, style_ranges = parse_markdown_formatting(text_content)

# Insert plain text
content_requests.append({
    'insertText': {
        'objectId': content_shape_id,
        'text': plain_text
    }
})

# Apply formatting for each range
for style_range in style_ranges:
    style_updates = {}
    if style_range.get('bold'):
        style_updates['bold'] = True
    if style_range.get('italic'):
        style_updates['italic'] = True
    
    if style_updates:
        content_requests.append({
            'updateTextStyle': {
                'objectId': content_shape_id,
                'textRange': {
                    'startIndex': style_range['start_index'],
                    'endIndex': style_range['end_index']
                },
                'style': style_updates,
                'fields': ','.join(style_updates.keys())
            }
        })
```

**Step 4: Handle nested formatting**
- `**bold *italic* bold**` should be handled correctly
- Track nested markers properly

**Implementation Notes:**
- Use regex or manual parsing to find `**text**` and `*text*` patterns
- Be careful with edge cases: `***text***` (bold+italic), `**text*text**` (invalid)
- Adjust indices after removing markdown markers

---

## Issue 2: Text Overlap

### Problem
Text overlaps on slides, making content unreadable. This can happen due to:
1. Placeholder text not being cleared before insertion
2. Text being too long for the shape bounds
3. Multiple insertions to the same shape
4. Font size too large
5. Line spacing issues

### Current Code Location
`utils/google_slides_exporter.py` lines 259-289

### Suggested Solutions

#### Solution 2A: Clear Placeholder Text First

**Problem**: Google Slides templates have placeholder text like "Click to add title" or "Click to add text". If we insert text without clearing, it can overlap.

**Fix**: Delete existing text before inserting new text.

```python
# Before inserting title:
if title_shape_id and slide_title:
    # First, get the current text length to delete it
    # Or use deleteText with a large endIndex to clear all
    content_requests.append({
        'deleteText': {
            'objectId': title_shape_id,
            'textRange': {
                'startIndex': 0,
                'endIndex': 1  # We'll need to get actual length, or use a large number
            }
        }
    })
    # Then insert new text
    content_requests.append({
        'insertText': {
            'objectId': title_shape_id,
            'text': slide_title
        }
    })
```

**Better approach**: Get the shape's current text length first:
```python
# Get slide details to find current text length
slide_details = service.presentations().pages().get(
    presentationId=presentation_id,
    pageObjectId=slide.get('objectId')
).execute()

# Find the shape and get its text length
# Then delete from 0 to text_length
```

#### Solution 2B: Use `insertionIndex` Parameter

**Problem**: If placeholder text exists, inserting at index 0 might cause overlap.

**Fix**: Insert at the end of existing text, or clear first.

```python
# Option 1: Insert at end (if we want to keep placeholder)
content_requests.append({
    'insertText': {
        'objectId': content_shape_id,
        'insertionIndex': existing_text_length,  # Insert at end
        'text': text_content
    }
})

# Option 2: Clear first, then insert (recommended)
content_requests.append({
    'deleteText': {
        'objectId': content_shape_id,
        'textRange': {
            'startIndex': 0,
            'endIndex': existing_text_length
        }
    }
})
content_requests.append({
    'insertText': {
        'objectId': content_shape_id,
        'insertionIndex': 0,
        'text': text_content
    }
})
```

#### Solution 2C: Adjust Font Size and Line Spacing

**Problem**: Text might be too large for the shape, causing overflow/overlap.

**Fix**: Set appropriate font size and line spacing after insertion.

```python
# After inserting text, adjust font size if needed
content_requests.append({
    'updateTextStyle': {
        'objectId': content_shape_id,
        'textRange': {
            'type': 'ALL'  # Apply to all text
        },
        'style': {
            'fontSize': {
                'magnitude': 14,  # Adjust based on content length
                'unit': 'PT'
            }
        },
        'fields': 'fontSize'
    }
})

# Adjust line spacing
content_requests.append({
    'updateParagraphStyle': {
        'objectId': content_shape_id,
        'textRange': {
            'type': 'ALL'
        },
        'style': {
            'lineSpacing': 1.2,  # 1.2x line spacing
            'spacingMode': 'SPACE_BETWEEN_LINES'
        },
        'fields': 'lineSpacing,spacingMode'
    }
})
```

#### Solution 2D: Truncate or Wrap Long Text

**Problem**: Text content might be too long for the slide.

**Fix**: 
1. Check text length before insertion
2. Truncate if too long, or split into multiple paragraphs
3. Use smaller font size for long content

```python
MAX_CHARS_PER_SLIDE = 500  # Adjust based on testing

if len(text_content) > MAX_CHARS_PER_SLIDE:
    # Option 1: Truncate with ellipsis
    text_content = text_content[:MAX_CHARS_PER_SLIDE - 3] + "..."
    
    # Option 2: Split into multiple paragraphs
    # (would require creating additional text boxes or slides)
    
    # Option 3: Use smaller font
    font_size = 12  # Instead of default 14
```

#### Solution 2E: Use Proper Bullet Point Formatting

**Problem**: Manual bullet points (`•`) might not align properly with Google Slides' native bullet formatting.

**Fix**: Use Google Slides' native bullet list formatting instead of manual `•` characters.

```python
# Instead of:
text_content = '\n'.join([f'• {point}' for point in bullet_points])

# Use native bullet formatting:
# 1. Insert text with line breaks (no manual bullets)
text_content = '\n'.join(bullet_points)

# 2. Apply bullet formatting to each line
for i, point in enumerate(bullet_points):
    line_start = sum(len(bullet_points[j]) + 1 for j in range(i))  # +1 for newline
    line_end = line_start + len(point)
    
    content_requests.append({
        'createParagraphBullets': {
            'objectId': content_shape_id,
            'textRange': {
                'startIndex': line_start,
                'endIndex': line_end
            },
            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
        }
    })
```

---

## Recommended Implementation Order

1. **Fix text overlap first** (Solution 2A + 2B):
   - Clear placeholder text before insertion
   - This is the most critical issue

2. **Add bold formatting** (Issue 1):
   - Implement markdown parser
   - Apply `updateTextStyle` requests
   - Test with various formatting combinations

3. **Fine-tune formatting** (Solution 2C + 2D + 2E):
   - Adjust font sizes
   - Use native bullet formatting
   - Handle long text gracefully

---

## Testing Checklist

After implementing fixes, test with:
- [ ] Slides with `**bold**` text
- [ ] Slides with `*italic*` text  
- [ ] Slides with nested formatting `**bold *italic* bold**`
- [ ] Slides with long text content
- [ ] Slides with many bullet points
- [ ] Title slides (first slide)
- [ ] Regular content slides
- [ ] Slides with both title and body content
- [ ] Verify no text overlap occurs
- [ ] Verify formatting is visually correct in Google Slides

---

## API Reference

- [Google Slides API - Formatting Text](https://developers.google.com/slides/api/guides/styling)
- [Google Slides API - updateTextStyle](https://developers.google.com/slides/api/reference/rest/v1/presentations/request#updatetextstylerequest)
- [Google Slides API - updateParagraphStyle](https://developers.google.com/slides/api/reference/rest/v1/presentations/request#updateparagraphstylerequest)
- [Google Slides API - deleteText](https://developers.google.com/slides/api/reference/rest/v1/presentations/request#deletetextrequest)

