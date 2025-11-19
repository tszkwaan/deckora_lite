"""
Utility functions for loading PDF content from URLs or local files.
Includes context compression to reduce token usage.
"""

from pypdf import PdfReader
import requests
from io import BytesIO
from pathlib import Path
import re
from typing import Optional, List, Tuple


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


def compress_report_content(
    content: str,
    enable_compression: bool = True,
    enable_summarization: bool = False,
    max_tokens: int = 50000,
    compression_ratio: float = 0.6
) -> str:
    """
    Compress report content by removing boilerplate and extracting main sections.
    
    This function:
    1. Extracts main sections (Introduction, Methods, Findings/Results, Discussion)
    2. Removes boilerplate (headers, footers, TOC, references, appendices)
    3. Handles chunking for very large documents (>max_tokens)
    4. Optionally summarizes content to reduce length
    
    Args:
        content: Raw PDF text content
        enable_compression: Whether to compress content (default: True)
        enable_summarization: Whether to summarize sections (default: False, requires LLM)
        max_tokens: Maximum tokens before chunking (default: 50000, ~37,500 chars)
        compression_ratio: Target compression ratio for summarization (0.5-0.7, default: 0.6)
        
    Returns:
        Compressed content string
    """
    if not enable_compression:
        return content
    
    # Estimate tokens (rough approximation: ~1.33 characters per token)
    estimated_tokens = len(content) / 1.33
    
    # Step 1: Remove common boilerplate patterns
    compressed = _remove_boilerplate(content)
    
    # Step 2: Extract main sections
    sections = _extract_main_sections(compressed)
    
    if not sections:
        # If section extraction fails, return cleaned content
        return compressed
    
    # Step 3: Combine extracted sections
    main_content = "\n\n".join([f"## {title}\n{text}" for title, text in sections])
    
    # Step 4: Handle chunking for very large documents
    if estimated_tokens > max_tokens:
        main_content = _chunk_large_content(main_content, max_tokens)
    
    # Step 5: Optional summarization (requires LLM - not implemented yet)
    if enable_summarization:
        # TODO: Implement LLM-based summarization
        # For now, just return compressed content
        pass
    
    return main_content


def _remove_boilerplate(content: str) -> str:
    """
    Remove common boilerplate elements from PDF content.
    
    Removes:
    - Headers and footers (page numbers, repeated titles)
    - Table of contents
    - References/Bibliography sections
    - Appendices
    - Copyright notices
    - Author affiliations (repeated)
    """
    lines = content.split('\n')
    cleaned_lines = []
    skip_section = False
    
    # Patterns to identify sections to skip
    skip_patterns = [
        r'^references?$',
        r'^bibliography$',
        r'^appendix\s+[a-z]?$',
        r'^table\s+of\s+contents?$',
        r'^contents?$',
        r'^acknowledgments?$',
        r'^acknowledgements?$',
        r'^copyright',
        r'^©\s*\d{4}',
    ]
    
    # Patterns for headers/footers (repeated text)
    header_footer_patterns = [
        r'^\d+\s*$',  # Page numbers alone
        r'^page\s+\d+',  # "Page X"
    ]
    
    seen_lines = set()
    consecutive_repeats = 0
    
    for i, line in enumerate(lines):
        line_stripped = line.strip().lower()
        
        # Skip empty lines
        if not line_stripped:
            cleaned_lines.append('')
            continue
        
        # Check if this is a section to skip
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                skip_section = True
                should_skip = True
                break
        
        if should_skip:
            continue
        
        # End skip section on next major heading (all caps or numbered)
        if skip_section:
            if re.match(r'^[A-Z\s]{3,}$', line.strip()) or re.match(r'^\d+\.', line.strip()):
                skip_section = False
            else:
                continue
        
        # Remove headers/footers (repeated lines)
        if line_stripped in seen_lines:
            consecutive_repeats += 1
            if consecutive_repeats > 2:  # Skip if repeated more than 2 times
                continue
        else:
            consecutive_repeats = 0
            seen_lines.add(line_stripped)
        
        # Skip page numbers
        is_page_number = False
        for pattern in header_footer_patterns:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                is_page_number = True
                break
        
        if not is_page_number:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def _extract_main_sections(content: str) -> List[Tuple[str, str]]:
    """
    Extract main sections from academic paper content.
    
    Looks for:
    - Introduction
    - Methods / Methodology
    - Results / Findings / Experimental Results
    - Discussion / Conclusion
    
    Returns:
        List of (section_title, section_content) tuples
    """
    sections = []
    
    # Common section title patterns (case-insensitive)
    section_patterns = [
        (r'^1\s*\.?\s*introduction', 'Introduction'),
        (r'^2\s*\.?\s*introduction', 'Introduction'),  # Sometimes numbered differently
        (r'^introduction', 'Introduction'),
        (r'^background', 'Introduction'),
        
        (r'^2\s*\.?\s*method', 'Methods'),
        (r'^3\s*\.?\s*method', 'Methods'),
        (r'^methodology', 'Methods'),
        (r'^methods?', 'Methods'),
        (r'^approach', 'Methods'),
        (r'^experimental\s+setup', 'Methods'),
        
        (r'^3\s*\.?\s*result', 'Results'),
        (r'^4\s*\.?\s*result', 'Results'),
        (r'^results?', 'Results'),
        (r'^findings?', 'Results'),
        (r'^experimental\s+results?', 'Results'),
        (r'^evaluation', 'Results'),
        
        (r'^4\s*\.?\s*discussion', 'Discussion'),
        (r'^5\s*\.?\s*discussion', 'Discussion'),
        (r'^discussion', 'Discussion'),
        (r'^conclusion', 'Discussion'),
        (r'^conclusions?', 'Discussion'),
        (r'^future\s+work', 'Discussion'),
    ]
    
    lines = content.split('\n')
    current_section = None
    current_content = []
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            if current_content:
                current_content.append('')
            continue
        
        # Check if this line is a section header
        found_section = None
        for pattern, section_name in section_patterns:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                # Save previous section if exists
                if current_section and current_content:
                    sections.append((current_section, '\n'.join(current_content).strip()))
                
                # Start new section
                current_section = section_name
                current_content = []
                found_section = True
                break
        
        if not found_section and current_section:
            # Add to current section
            current_content.append(line)
        elif not current_section:
            # Content before first section - could be abstract or intro
            # Check if it looks like abstract
            if re.match(r'^abstract', line_stripped, re.IGNORECASE):
                continue  # Skip abstract
            # Otherwise, start Introduction section
            if not current_section:
                current_section = 'Introduction'
                current_content = [line]
    
    # Add final section
    if current_section and current_content:
        sections.append((current_section, '\n'.join(current_content).strip()))
    
    # If no sections found, return content as single "Main Content" section
    if not sections:
        return [('Main Content', content)]
    
    return sections


def _chunk_large_content(content: str, max_tokens: int) -> str:
    """
    Chunk large content to fit within token limit.
    
    For documents exceeding max_tokens, keeps:
    1. First N sections that fit
    2. Summary of remaining sections
    
    Args:
        content: Content to chunk
        max_tokens: Maximum tokens allowed
        
    Returns:
        Chunked content
    """
    max_chars = int(max_tokens * 1.33)  # Convert tokens to chars
    
    if len(content) <= max_chars:
        return content
    
    # Split by sections (marked by ##)
    sections = re.split(r'\n##\s+', content)
    
    if len(sections) == 1:
        # No clear sections, just truncate
        return content[:max_chars] + "\n\n[... Content truncated due to length ...]"
    
    # Keep sections until we hit the limit
    result_sections = []
    current_length = 0
    
    for section in sections:
        section_with_header = f"## {section}" if not section.startswith('##') else section
        section_length = len(section_with_header)
        
        if current_length + section_length <= max_chars:
            result_sections.append(section_with_header)
            current_length += section_length
        else:
            # Truncate this section if needed
            remaining = max_chars - current_length
            if remaining > 100:  # Only add if meaningful space left
                truncated = section[:remaining] + "\n\n[... Section truncated ...]"
                result_sections.append(f"## {truncated}")
            break
    
    if len(result_sections) < len(sections):
        result_sections.append("\n\n[... Additional sections omitted due to length ...]")
    
    return '\n\n'.join(result_sections)


def load_pdf(
    report_url: str = None,
    report_file: str = None,
    compress: bool = True,
    enable_summarization: bool = False
) -> str:
    """
    Load PDF content from either URL or local file, with optional compression.
    
    Args:
        report_url: URL to the PDF file (optional)
        report_file: Path to local PDF file (optional)
        compress: Whether to compress content (default: True)
        enable_summarization: Whether to summarize sections (default: False)
        
    Returns:
        Extracted text content from all pages (compressed if enabled)
        
    Raises:
        ValueError: If neither report_url nor report_file is provided
    """
    if report_url:
        content = load_pdf_from_url(report_url)
    elif report_file:
        content = load_pdf_from_file(report_file)
    else:
        raise ValueError("Either report_url or report_file must be provided")
    
    # Apply compression if enabled
    if compress:
        original_length = len(content)
        content = compress_report_content(content, enable_compression=True, enable_summarization=enable_summarization)
        compressed_length = len(content)
        compression_ratio = compressed_length / original_length if original_length > 0 else 1.0
        print(f"📦 Compressed PDF content: {original_length:,} → {compressed_length:,} chars ({compression_ratio:.1%})")
    
    return content

