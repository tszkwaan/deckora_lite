# How Open Peeps Image System Works

## Current State

**Yes, it only searches the 5 sample SVGs we have locally.**

We created 5 sample SVG files for testing:
- `analytics-chart.svg`
- `computer-person.svg`
- `research-science.svg`
- `security-shield.svg`
- `warning-alert.svg`

## How It Works in the Pipeline

### 1. **On-the-Fly Search (Yes)**
When the LLM provides keywords (like `icons_suggested: ['security', 'warning', 'lock']`), the system:

1. **Calls `get_image_url(keyword, source="peeps")`** in `image_helper.py`
2. **Which calls `get_peeps_image_url(keyword)`** in `search_utils.py`
3. **Which performs FAISS semantic search** using the pre-built index
4. **Returns the best matching SVG path** (e.g., `/svgs/security-shield.svg`)

### 2. **Semantic Search (Not Exact Match)**
The system uses **FAISS + sentence-transformers** for semantic search:
- Keywords are converted to embeddings (384-dimensional vectors)
- Compared against pre-computed embeddings of all SVG filenames
- Returns the **semantically closest match**, not exact string match

**Example:**
- Keyword: `"lock"` → Matches `security-shield.svg` (score: 0.860)
- Keyword: `"shield"` → Matches `security-shield.svg` (score: 0.956)
- Keyword: `"data"` → Matches `analytics-chart.svg` (score: 0.885)

### 3. **Search Flow**

```
LLM generates slide with icons_suggested: ['security', 'warning']
    ↓
web_slides_generator_tool.py processes icons_suggested
    ↓
Calls get_image_url('security', source='peeps')
    ↓
search_utils.get_peeps_image_url('security')
    ↓
FAISS semantic search (on-the-fly, <1ms)
    ↓
Returns: /svgs/security-shield.svg
    ↓
Embedded in HTML: <img src="/svgs/security-shield.svg" ...>
```

## Current Limitation

**Only 5 SVGs available** because:
1. We created sample SVGs for testing
2. The actual Open Peeps repository structure is different than expected
3. We haven't downloaded the full Open Peeps library yet

## How to Expand

### Option 1: Download More Open Peeps SVGs
1. Manually download Open Peeps SVGs from:
   - [Open Peeps Generator](https://www.opeeps.fun/) - generate and download
   - [IconScout](https://iconscout.com/illustrations/open-peeps) - browse and download
2. Place them in `presentation_agent/assets/peeps/svgs/`
3. Run `python3 download_peeps.py` to update metadata
4. Run `python3 build_index.py` to rebuild the FAISS index

### Option 2: Use React Peeps Library
The [react-peeps](https://github.com/CeamKrier/react-peeps) library has programmatic access to Open Peeps components. We could:
1. Extract SVG generation logic
2. Generate SVGs on-demand based on keywords
3. Cache generated SVGs locally

### Option 3: Keep Current System (Recommended for Competition)
- 5 SVGs is enough for a prototype
- Semantic search ensures good keyword matching
- Fast and local (no API calls)
- Can expand later if needed

## Search Quality

Even with only 5 SVGs, the semantic search works well:
- `"security"`, `"lock"`, `"shield"` → `security-shield.svg` ✅
- `"warning"`, `"alert"` → `warning-alert.svg` ✅
- `"analytics"`, `"data"`, `"chart"` → `analytics-chart.svg` ✅
- `"research"`, `"science"`, `"ai"` → `research-science.svg` ✅
- `"computer"`, `"device"`, `"technology"` → `computer-person.svg` ✅

## Performance

- **Index loading**: ~1-2 seconds (first call, then cached)
- **Search time**: <1ms (FAISS is very fast)
- **Memory**: ~5MB (for 5 SVGs + embeddings)

## Summary

✅ **On-the-fly search**: Yes, searches when keywords are provided  
✅ **Semantic matching**: Uses FAISS for intelligent keyword matching  
⚠️ **Limited to 5 SVGs**: Currently only sample SVGs, but system is designed to scale  
✅ **Fast**: Sub-millisecond search once index is loaded  
✅ **Local**: No external API calls, completely free

