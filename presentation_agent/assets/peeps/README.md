# Open Peeps Illustration Search API

A local, free illustration search system using Open Peeps SVGs with semantic search.

## Quick Start

### 1. Install Dependencies

```bash
pip install sentence-transformers faiss-cpu numpy fastapi uvicorn requests
```

### 2. Download Open Peeps SVGs

```bash
cd presentation_agent/assets/peeps
python download_peeps.py
```

This will:
- Download all SVG files from Open Peeps GitHub repository
- Save them to `svgs/` folder
- Create `metadata.json` with file information

### 3. Build Search Index

```bash
python build_index.py
```

This will:
- Generate embeddings for all SVG filenames
- Build FAISS search index
- Save index files (`peeps_index.faiss`, `peeps_index.pkl`)

### 4. Start API Server

```bash
python search_api.py
```

Server runs on `http://localhost:8000`

### 5. Test Search

```bash
curl "http://localhost:8000/api/peeps/search?query=security&limit=5"
```

## API Endpoints

### Search Illustrations

```
GET /api/peeps/search?query={keyword}&limit={n}
```

**Parameters:**
- `query` (required): Search keyword
- `limit` (optional, default=5): Number of results (1-20)

**Response:**
```json
{
  "query": "security",
  "results": [
    {
      "name": "shield-peep-01.svg",
      "score": 0.86,
      "url": "/assets/peeps/svgs/shield-peep-01.svg",
      "path": "presentation_agent/assets/peeps/svgs/shield-peep-01.svg"
    }
  ],
  "total_found": 5
}
```

### Health Check

```
GET /api/peeps/health
```

## Integration with Deckora

The system is integrated via `image_helper.py`:

```python
from presentation_agent.assets.peeps.search_api import search_peeps_local

# Search for illustration
results = search_peeps_local("security", limit=1)
if results:
    image_url = results[0]['url']  # "/assets/peeps/svgs/..."
```

## File Structure

```
presentation_agent/assets/peeps/
├── svgs/                    # SVG files (downloaded)
├── metadata.json            # File metadata
├── peeps_index.faiss        # FAISS vector index
├── peeps_index.pkl          # Index metadata
├── download_peeps.py        # Download script
├── build_index.py           # Index builder
├── search_api.py            # FastAPI server
└── README.md                # This file
```

## Re-indexing

When new SVGs are added:

```bash
python download_peeps.py  # Download new files
python build_index.py     # Rebuild index
```

## Notes

- **Free & Local**: No API keys, no external services
- **Fast**: FAISS provides sub-millisecond search
- **Semantic**: Uses embeddings for meaning-based search
- **License**: Open Peeps is CC0 (Public Domain)

