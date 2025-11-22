#!/bin/bash
# Setup script for Open Peeps illustration search system

echo "=========================================="
echo "Open Peeps Setup"
echo "=========================================="

# Check if dependencies are installed
echo "Checking dependencies..."
python3 -c "import sentence_transformers, faiss, fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install sentence-transformers faiss-cpu numpy fastapi uvicorn requests
else
    echo "✅ Dependencies already installed"
fi

# Step 1: Download SVGs
echo ""
echo "Step 1: Downloading Open Peeps SVGs..."
python3 download_peeps.py

# Step 2: Build index
echo ""
echo "Step 2: Building search index..."
python3 build_index.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the API server:"
echo "  python3 search_api.py"
echo ""
echo "To test search:"
echo "  curl 'http://localhost:8000/api/peeps/search?query=security'"

