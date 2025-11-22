"""
Utility functions for local Open Peeps search (without API server).

This allows direct FAISS search without running a separate API server.
"""

import pickle
from pathlib import Path
from typing import List, Dict, Optional
import logging

try:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
except ImportError:
    logging.warning("FAISS or sentence-transformers not installed. Install with: pip install faiss-cpu sentence-transformers numpy")

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
INDEX_FILE = BASE_DIR / "peeps_index.faiss"
METADATA_INDEX_FILE = BASE_DIR / "peeps_index.pkl"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Global cache
_index_cache = None
_metadata_cache = None
_model_cache = None


def _load_index_if_needed():
    """Lazy load index and model."""
    global _index_cache, _metadata_cache, _model_cache
    
    if _index_cache is None:
        if not INDEX_FILE.exists() or not METADATA_INDEX_FILE.exists():
            logger.warning("Open Peeps index not found. Run build_index.py first.")
            return None, None, None
        
        try:
            _index_cache = faiss.read_index(str(INDEX_FILE))
            with open(METADATA_INDEX_FILE, 'rb') as f:
                _metadata_cache = pickle.load(f)
            _model_cache = SentenceTransformer(MODEL_NAME)
            logger.info(f"Loaded Open Peeps index with {_index_cache.ntotal} illustrations")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return None, None, None
    
    return _index_cache, _metadata_cache, _model_cache


def search_peeps_local(query: str, limit: int = 5) -> List[Dict]:
    """
    Search Open Peeps illustrations locally (without API server).
    
    Args:
        query: Search keyword
        limit: Number of results (default: 5)
        
    Returns:
        List of dicts with 'name', 'score', 'url', 'path'
    """
    index, metadata, model = _load_index_if_needed()
    
    if index is None or model is None:
        logger.warning("Index not available. Returning empty results.")
        return []
    
    # Generate query embedding
    query_embedding = model.encode([query])
    query_embedding = np.array(query_embedding).astype('float32')
    
    # Search
    k = min(limit, index.ntotal)
    distances, indices = index.search(query_embedding, k)
    
    # Build results
    results = []
    for distance, idx in zip(distances[0], indices[0]):
        if idx < len(metadata):
            file_info = metadata[idx]
            
            # Convert distance to score (0-1, higher is better)
            max_distance = 10.0
            score = max(0.0, 1.0 - (distance / max_distance))
            score = min(1.0, score)
            
            # Build URL path
            relative_path = file_info['path']
            url_path = f"/{relative_path.replace('presentation_agent/', '')}"
            
            results.append({
                "name": file_info['name'],
                "score": round(float(score), 3),
                "url": url_path,
                "path": relative_path
            })
    
    return results


def get_peeps_image_url(keyword: str) -> Optional[str]:
    """
    Get best matching Open Peeps image URL for a keyword.
    
    Args:
        keyword: Search keyword (e.g., "security", "warning")
        
    Returns:
        URL path to SVG file, or None if not found
    """
    results = search_peeps_local(keyword, limit=1)
    if results:
        return results[0]['url']
    return None

