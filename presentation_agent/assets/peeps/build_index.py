"""
Build FAISS search index for Open Peeps illustrations.

This script:
1. Loads all SVG filenames from metadata
2. Generates embeddings using sentence-transformers
3. Builds FAISS index for fast similarity search
4. Saves index files for API server
"""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import logging

# Type stubs for optional dependencies
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print("❌ Missing dependencies. Install with:")
    print("   pip install sentence-transformers faiss-cpu numpy")
    print(f"   Error: {e}")
    DEPENDENCIES_AVAILABLE = False
    # Create type stubs
    SentenceTransformer = Any
    faiss = Any
    np = Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
METADATA_FILE = BASE_DIR / "metadata.json"
INDEX_FILE = BASE_DIR / "peeps_index.faiss"
METADATA_INDEX_FILE = BASE_DIR / "peeps_index.pkl"

# Embedding model (lightweight, free, local)
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def extract_keywords_from_filename(filename: str) -> str:
    """
    Extract searchable keywords from SVG filename.
    
    Example: "sitting-peep-01.svg" -> "sitting peep person character"
    """
    # Remove extension and split by hyphens/underscores
    name = filename.replace('.svg', '').lower()
    parts = name.replace('_', '-').split('-')
    
    # Common Open Peeps naming patterns
    keywords = []
    for part in parts:
        if part not in ['peep', 'peeps', '01', '02', '03', '1', '2', '3']:
            keywords.append(part)
    
    # Add common terms
    if 'peep' in name or 'peeps' in name:
        keywords.extend(['person', 'character', 'illustration'])
    
    return ' '.join(keywords) if keywords else name


def load_metadata() -> Dict:
    """Load metadata.json file."""
    if not METADATA_FILE.exists():
        logger.error(f"Metadata file not found: {METADATA_FILE}")
        logger.info("Run download_peeps.py first to download SVGs")
        return {'files': []}
    
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_search_index() -> Tuple[Optional[Any], List[Dict]]:
    """
    Build FAISS index from SVG metadata.
    
    Returns:
        (faiss_index, file_metadata_list)
    """
    logger.info("Loading metadata...")
    metadata = load_metadata()
    
    if not metadata.get('files'):
        logger.warning("No files in metadata. Run download_peeps.py first.")
        return None, []
    
    logger.info(f"Found {len(metadata['files'])} SVG files")
    
    # Load embedding model
    logger.info(f"Loading embedding model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    # Prepare texts and metadata
    texts = []
    file_metadata = []
    
    for file_info in metadata['files']:
        filename = file_info['name']
        searchable_text = extract_keywords_from_filename(filename)
        texts.append(searchable_text)
        file_metadata.append({
            'name': filename,
            'path': file_info['path'],
            'searchable_text': searchable_text
        })
    
    logger.info("Generating embeddings...")
    try:
        embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        embeddings = np.array(embeddings).astype('float32')
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        # Fallback: try without progress bar
        embeddings = model.encode(texts, convert_to_numpy=True)
        embeddings = np.array(embeddings).astype('float32')
    
    # Build FAISS index
    dimension = embeddings.shape[1]
    logger.info(f"Building FAISS index (dimension: {dimension})...")
    
    # Use L2 (Euclidean) distance index
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    logger.info(f"✅ Index built with {index.ntotal} vectors")
    
    return index, file_metadata


def save_index(index: faiss.Index, file_metadata: List[Dict]):
    """Save FAISS index and metadata."""
    logger.info("Saving index files...")
    
    # Save FAISS index
    faiss.write_index(index, str(INDEX_FILE))
    logger.info(f"✅ Saved FAISS index: {INDEX_FILE}")
    
    # Save metadata
    with open(METADATA_INDEX_FILE, 'wb') as f:
        pickle.dump(file_metadata, f)
    logger.info(f"✅ Saved index metadata: {METADATA_INDEX_FILE}")


def main():
    """Main function to build and save search index."""
    if not DEPENDENCIES_AVAILABLE:
        exit(1)
    
    print("=" * 60)
    print("Open Peeps Search Index Builder")
    print("=" * 60)
    
    index, file_metadata = build_search_index()
    
    if index is None:
        print("\n❌ Failed to build index. Check metadata file.")
        return
    
    save_index(index, file_metadata)
    
    print("\n✅ Index build complete!")
    print(f"📁 Index file: {INDEX_FILE}")
    print(f"📄 Metadata file: {METADATA_INDEX_FILE}")
    print(f"🔍 Ready for search with {index.ntotal} illustrations")


if __name__ == "__main__":
    main()

