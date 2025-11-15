"""
Utility functions for loading PDF content from URLs or local files.
"""

from pypdf import PdfReader
import requests
from io import BytesIO
from pathlib import Path


def load_pdf_from_url(url: str) -> str:
    """
    Load PDF content from a URL.
    
    Args:
        url: URL to the PDF file
        
    Returns:
        Extracted text content from all pages
    """
    response = requests.get(url)
    response.raise_for_status()
    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text


def load_pdf_from_file(file_path: str) -> str:
    """
    Load PDF content from a local file.
    
    Args:
        file_path: Path to the local PDF file
        
    Returns:
        Extracted text content from all pages
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text


def load_pdf(report_url: str = None, report_file: str = None) -> str:
    """
    Load PDF content from either URL or local file.
    
    Args:
        report_url: URL to the PDF file (optional)
        report_file: Path to local PDF file (optional)
        
    Returns:
        Extracted text content from all pages
        
    Raises:
        ValueError: If neither report_url nor report_file is provided
    """
    if report_url:
        return load_pdf_from_url(report_url)
    elif report_file:
        return load_pdf_from_file(report_file)
    else:
        raise ValueError("Either report_url or report_file must be provided")

