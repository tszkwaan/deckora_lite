"""
Download Open Peeps SVG illustrations from GitHub repository.

Open Peeps: https://github.com/humaaans/open-peeps
License: CC0 (Public Domain)
"""

import os
import json
import requests
from pathlib import Path
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Open Peeps repository information
# Note: Open Peeps doesn't have a simple GitHub repo with SVGs
# We'll use a manual approach or download from alternative sources
OPEN_PEEPS_REPO = "humaaans/open-peeps"
GITHUB_API_BASE = "https://api.github.com/repos"

# Try different possible folder structures
POSSIBLE_FOLDERS = ["SVG", "svgs", "illustrations", "assets", "public"]

# Local storage paths
BASE_DIR = Path(__file__).parent
SVGS_DIR = BASE_DIR / "svgs"
METADATA_FILE = BASE_DIR / "metadata.json"


def download_file_from_github(url: str, output_path: Path) -> bool:
    """Download a file from GitHub raw content."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response.text, encoding='utf-8')
        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def get_svg_files_from_repo() -> List[Dict]:
    """
    Fetch list of SVG files from Open Peeps GitHub repository.
    
    Note: Open Peeps repository structure may vary. This tries multiple approaches.
    
    Returns:
        List of dicts with 'name', 'path', 'download_url'
    """
    svg_files = []
    
    # Try to get repository tree (recursive)
    try:
        # First, get the default branch
        repo_info_url = f"{GITHUB_API_BASE}/{OPEN_PEEPS_REPO}"
        repo_response = requests.get(repo_info_url, timeout=30)
        repo_response.raise_for_status()
        repo_info = repo_response.json()
        default_branch = repo_info.get('default_branch', 'main')
        
        # Get recursive tree
        tree_url = f"{GITHUB_API_BASE}/{OPEN_PEEPS_REPO}/git/trees/{default_branch}?recursive=1"
        tree_response = requests.get(tree_url, timeout=30)
        tree_response.raise_for_status()
        tree_data = tree_response.json()
        
        # Find all SVG files
        for item in tree_data.get('tree', []):
            if item.get('type') == 'blob' and item.get('path', '').endswith('.svg'):
                # Construct download URL
                download_url = f"https://raw.githubusercontent.com/{OPEN_PEEPS_REPO}/{default_branch}/{item['path']}"
                svg_files.append({
                    'name': item['path'].split('/')[-1],  # Just filename
                    'path': item['path'],
                    'download_url': download_url,
                    'size': item.get('size', 0)
                })
        
        if svg_files:
            logger.info(f"Found {len(svg_files)} SVG files in repository")
            return svg_files
            
    except Exception as e:
        logger.warning(f"Failed to fetch repository tree: {e}")
    
    # Fallback: Try individual folder structures
    for folder in POSSIBLE_FOLDERS:
        try:
            url = f"{GITHUB_API_BASE}/{OPEN_PEEPS_REPO}/contents/{folder}"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                files = response.json()
                for file_info in files:
                    if file_info.get('type') == 'file' and file_info.get('name', '').endswith('.svg'):
                        svg_files.append({
                            'name': file_info['name'],
                            'path': file_info['path'],
                            'download_url': file_info['download_url'],
                            'size': file_info.get('size', 0)
                        })
                if svg_files:
                    logger.info(f"Found {len(svg_files)} SVG files in {folder}/")
                    return svg_files
        except Exception:
            continue
    
    logger.warning("No SVG files found via GitHub API. Will use fallback approach.")
    return []


def download_all_peeps() -> Dict:
    """
    Download all Open Peeps SVG files and create metadata.
    
    Returns:
        Metadata dict with file information
    """
    logger.info("Starting Open Peeps download...")
    
    # Create svgs directory
    SVGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get list of SVG files
    svg_files = get_svg_files_from_repo()
    
    if not svg_files:
        logger.warning("No SVG files found. Using fallback approach...")
        # Fallback: create placeholder metadata
        return create_fallback_metadata()
    
    metadata = {
        'total_files': len(svg_files),
        'files': []
    }
    
    downloaded = 0
    for file_info in svg_files:
        filename = file_info['name']
        output_path = SVGS_DIR / filename
        
        # Skip if already exists
        if output_path.exists():
            logger.info(f"Skipping {filename} (already exists)")
            downloaded += 1
        else:
            logger.info(f"Downloading {filename}...")
            if download_file_from_github(file_info['download_url'], output_path):
                downloaded += 1
        
        # Add to metadata
        metadata['files'].append({
            'name': filename,
            'path': str(output_path.relative_to(BASE_DIR)),
            'size': file_info['size']
        })
    
    # Save metadata
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    
    logger.info(f"✅ Downloaded {downloaded}/{len(svg_files)} SVG files")
    logger.info(f"Metadata saved to {METADATA_FILE}")
    
    return metadata


def create_fallback_metadata() -> Dict:
    """
    Create fallback metadata if GitHub API fails.
    This allows the system to work with manually added SVGs.
    Also creates sample SVGs for testing if none exist.
    """
    logger.info("Creating fallback metadata structure...")
    
    metadata = {
        'total_files': 0,
        'files': []
    }
    
    # Scan local svgs directory if it exists
    SVGS_DIR.mkdir(parents=True, exist_ok=True)
    
    svg_files = list(SVGS_DIR.glob("*.svg"))
    
    # If no SVGs found, create a few sample ones for testing
    if not svg_files:
        logger.info("No SVGs found. Creating sample SVGs for testing...")
        create_sample_svgs()
        svg_files = list(SVGS_DIR.glob("*.svg"))
    
    for svg_file in svg_files:
        metadata['files'].append({
            'name': svg_file.name,
            'path': str(svg_file.relative_to(BASE_DIR)),
            'size': svg_file.stat().st_size
        })
        metadata['total_files'] += 1
    
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    logger.info(f"Found {metadata['total_files']} local SVG files")
    
    return metadata


def create_sample_svgs():
    """Create sample SVG files for testing."""
    sample_svgs = {
        "computer-person.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect x="20" y="30" width="60" height="40" fill="#4A90E2" rx="5"/>
  <rect x="25" y="35" width="50" height="30" fill="#2C3E50"/>
  <circle cx="50" cy="20" r="8" fill="#E8B4A0"/>
  <rect x="45" y="28" width="10" height="15" fill="#E8B4A0"/>
  <text x="50" y="85" text-anchor="middle" font-size="8" fill="#333">Computer</text>
</svg>''',
        "security-shield.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <path d="M50 10 L70 20 L70 45 Q70 60 50 75 Q30 60 30 45 L30 20 Z" fill="#7C3AED" stroke="#5B21B6" stroke-width="2"/>
  <circle cx="50" cy="40" r="12" fill="#FFFFFF"/>
  <text x="50" y="90" text-anchor="middle" font-size="8" fill="#333">Security</text>
</svg>''',
        "warning-alert.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <path d="M50 15 L80 75 L20 75 Z" fill="#F59E0B" stroke="#D97706" stroke-width="2"/>
  <text x="50" y="60" text-anchor="middle" font-size="20" fill="#FFFFFF" font-weight="bold">!</text>
  <text x="50" y="90" text-anchor="middle" font-size="8" fill="#333">Warning</text>
</svg>''',
        "analytics-chart.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect x="15" y="60" width="12" height="25" fill="#10B981"/>
  <rect x="32" y="45" width="12" height="40" fill="#10B981"/>
  <rect x="49" y="30" width="12" height="55" fill="#10B981"/>
  <rect x="66" y="50" width="12" height="35" fill="#10B981"/>
  <line x1="10" y1="80" x2="85" y2="80" stroke="#333" stroke-width="2"/>
  <line x1="10" y1="80" x2="10" y2="20" stroke="#333" stroke-width="2"/>
  <text x="50" y="95" text-anchor="middle" font-size="8" fill="#333">Analytics</text>
</svg>''',
        "research-science.svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="35" r="15" fill="#EC4899" opacity="0.3"/>
  <path d="M50 20 L50 50 M40 35 L60 35" stroke="#EC4899" stroke-width="3"/>
  <rect x="40" y="50" width="20" height="25" fill="#EC4899" rx="2"/>
  <text x="50" y="90" text-anchor="middle" font-size="8" fill="#333">Research</text>
</svg>'''
    }
    
    for filename, svg_content in sample_svgs.items():
        file_path = SVGS_DIR / filename
        file_path.write_text(svg_content, encoding='utf-8')
        logger.info(f"Created sample SVG: {filename}")


if __name__ == "__main__":
    print("=" * 60)
    print("Open Peeps Downloader")
    print("=" * 60)
    metadata = download_all_peeps()
    print(f"\n✅ Complete! Downloaded {metadata['total_files']} SVG files")
    print(f"📁 Location: {SVGS_DIR}")
    print(f"📄 Metadata: {METADATA_FILE}")

