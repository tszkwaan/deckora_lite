# Open Peeps Illustration Search API - Tech Plan

## Overview
Build a local, free illustration search system using Open Peeps SVGs with semantic search capabilities.

## Architecture

### 1. Data Layer
- **Source**: Open Peeps GitHub repository (CC0 licensed)
- **Storage**: `presentation_agent/assets/peeps/svgs/` (SVG files)
- **Metadata**: `presentation_agent/assets/peeps/metadata.json` (file names, descriptions)

### 2. Embedding Layer
- **Model**: `sentence-transformers/all-MiniLM-L6-v2` (free, local, lightweight)
- **Process**: Generate embeddings for each SVG filename + description
- **Storage**: FAISS index file (`presentation_agent/assets/peeps/peeps_index.faiss`)

### 3. Search Layer
- **Index**: FAISS (Facebook AI Similarity Search) - fast, local
- **Method**: Cosine similarity between query embedding and SVG embeddings
- **Fallback**: Fuzzy string matching for exact name matches

### 4. API Layer
- **Framework**: FastAPI (lightweight, async)
- **Endpoint**: `GET /api/peeps/search?query={keyword}`
- **Response**: JSON with results sorted by similarity score

### 5. Integration Layer
- **Update**: `presentation_agent/templates/image_helper.py`
- **Change**: `get_image_url()` → `get_peeps_image_url()` for local SVG paths

## File Structure
```
presentation_agent/assets/peeps/
├── svgs/                    # Downloaded SVG files
├── metadata.json            # SVG metadata (name, description)
├── peeps_index.faiss        # FAISS vector index
├── peeps_index.pkl          # FAISS index metadata
├── download_peeps.py        # Script to download SVGs
├── build_index.py           # Script to generate embeddings & FAISS index
└── search_api.py            # FastAPI server
```

## Implementation Steps

1. **Download Script** (`download_peeps.py`)
   - Clone/download Open Peeps SVGs from GitHub
   - Organize files in `svgs/` folder
   - Generate metadata.json with filenames

2. **Index Builder** (`build_index.py`)
   - Load all SVG filenames
   - Generate embeddings using sentence-transformers
   - Build FAISS index
   - Save index files

3. **API Server** (`search_api.py`)
   - FastAPI server with search endpoint
   - Load FAISS index on startup
   - Handle search queries
   - Return local file paths

4. **Integration** (`image_helper.py`)
   - Add `get_peeps_image_url()` function
   - Call local API or use direct FAISS search
   - Return local SVG paths

## Dependencies
- `sentence-transformers` - For embeddings
- `faiss-cpu` - For vector search (or `faiss` if GPU available)
- `fastapi` - For API server
- `uvicorn` - For running FastAPI server

## Usage Flow
1. Run `download_peeps.py` once to download SVGs
2. Run `build_index.py` once to build search index
3. Start API server: `python search_api.py`
4. System calls API or uses direct search function
5. Returns local SVG path: `/assets/peeps/svgs/{filename}.svg`

