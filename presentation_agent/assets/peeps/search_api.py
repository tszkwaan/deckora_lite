"""
FastAPI server for Open Peeps illustration search.

Endpoints:
- GET /api/peeps/search?query={keyword}&limit={n}
- GET /api/peeps/health
"""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Optional
import logging

try:
    from fastapi import FastAPI, Query, HTTPException
    from fastapi.responses import JSONResponse
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    import uvicorn
except ImportError:
    print("❌ Missing dependencies. Install with:")
    print("   pip install fastapi uvicorn sentence-transformers faiss-cpu numpy")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Open Peeps Search API", version="1.0.0")

# Paths
BASE_DIR = Path(__file__).parent
INDEX_FILE = BASE_DIR / "peeps_index.faiss"
METADATA_INDEX_FILE = BASE_DIR / "peeps_index.pkl"
SVGS_DIR = BASE_DIR / "svgs"

# Global variables (loaded on startup)
faiss_index = None
file_metadata = None
embedding_model = None
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_index():
    """Load FAISS index and metadata on startup."""
    global faiss_index, file_metadata, embedding_model
    
    if not INDEX_FILE.exists() or not METADATA_INDEX_FILE.exists():
        logger.warning("Index files not found. Run build_index.py first.")
        return False
    
    try:
        logger.info("Loading FAISS index...")
        faiss_index = faiss.read_index(str(INDEX_FILE))
        
        logger.info("Loading index metadata...")
        with open(METADATA_INDEX_FILE, 'rb') as f:
            file_metadata = pickle.load(f)
        
        logger.info("Loading embedding model...")
        embedding_model = SentenceTransformer(MODEL_NAME)
        
        logger.info(f"✅ Loaded index with {faiss_index.ntotal} illustrations")
        return True
    except Exception as e:
        logger.error(f"Failed to load index: {e}")
        return False


@app.on_event("startup")
async def startup_event():
    """Load index on server startup."""
    if not load_index():
        logger.warning("⚠️  Server starting without index. Run build_index.py first.")


@app.get("/api/peeps/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "index_loaded": faiss_index is not None,
        "total_illustrations": faiss_index.ntotal if faiss_index else 0
    }


@app.get("/api/peeps/search")
async def search_peeps(
    query: str = Query(..., description="Search keyword"),
    limit: int = Query(5, ge=1, le=20, description="Number of results")
) -> Dict:
    """
    Search Open Peeps illustrations by keyword.
    
    Returns:
        {
            "query": "...",
            "results": [
                {
                    "name": "sitting-peep-01.svg",
                    "score": 0.86,
                    "url": "/assets/peeps/svgs/sitting-peep-01.svg",
                    "path": "presentation_agent/assets/peeps/svgs/sitting-peep-01.svg"
                },
                ...
            ]
        }
    """
    if faiss_index is None or embedding_model is None:
        raise HTTPException(
            status_code=503,
            detail="Search index not loaded. Run build_index.py first."
        )
    
    # Generate query embedding
    query_embedding = embedding_model.encode([query])
    query_embedding = np.array(query_embedding).astype('float32')
    
    # Search in FAISS index
    k = min(limit, faiss_index.ntotal)
    distances, indices = faiss_index.search(query_embedding, k)
    
    # Build results
    results = []
    for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < len(file_metadata):
            file_info = file_metadata[idx]
            
            # Convert L2 distance to similarity score (0-1, higher is better)
            # L2 distance: lower is better, so we invert it
            max_distance = 10.0  # Approximate max distance for normalization
            score = max(0.0, 1.0 - (distance / max_distance))
            score = min(1.0, score)  # Cap at 1.0
            
            # Build URL path (relative to project root)
            relative_path = file_info['path']
            url_path = f"/{relative_path.replace('presentation_agent/', '')}"
            
            results.append({
                "name": file_info['name'],
                "score": round(float(score), 3),
                "url": url_path,
                "path": relative_path,
                "distance": float(distance)
            })
    
    return {
        "query": query,
        "results": results,
        "total_found": len(results)
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Open Peeps Search API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/api/peeps/search?query={keyword}",
            "health": "/api/peeps/health"
        },
        "status": "running" if faiss_index else "index_not_loaded"
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Open Peeps Search API Server")
    print("=" * 60)
    print("Starting server on http://localhost:8000")
    print("API docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

