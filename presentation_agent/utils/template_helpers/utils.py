"""
Shared utility functions for template helpers.
"""

import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Singleton loader instance
_loader = None

def _get_loader():
    """Get or create the singleton TemplateLoader instance."""
    global _loader
    if _loader is None:
        from presentation_agent.utils.template_loader import TemplateLoader
        _loader = TemplateLoader()
    return _loader


def highlight_numbers_in_text(text: str, primary_color: str) -> str:
    """
    Automatically highlight STATISTICAL numbers in text with brand color and larger font.
    Skips numbers that are part of model names/versions (e.g., "GPT-4", "v2.0", "3.5-turbo").
    
    Works for: integers, decimals, comma-separated numbers, percentages, k/m suffixes.
    
    Examples:
    - "5 scenarios" → highlights "5" (statistic)
    - "700,000 prompts" → highlights "700,000" (statistic)
    - "25% improvement" → highlights "25%" (statistic)
    - "$2.5M revenue" → highlights "2.5M" (statistic)
    - "GPT-4" → does NOT highlight "4" (model name)
    - "GPT-3.5-turbo" → does NOT highlight "3.5" (model version)
    - "v2.0" → does NOT highlight "2.0" (version number)
    
    Args:
        text: Text string to process
        primary_color: Brand color for highlighting (hex code)
        
    Returns:
        Text with statistical numbers wrapped in <span> tags for styling
    """
    # Pattern to match various number formats:
    # - Integers: 5, 10, 100
    # - Decimals: 2.5, 0.25
    # - Comma-separated: 700,000, 1,234,567
    # - Percentages: 25%, 100%
    # - With k/m suffixes: 700k, 2.5M
    # - With currency: $2.5M, $100
    # - Combined: $2.5M, 25%, 700,000
    pattern = r'\b(\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?[km]?%?)\b'
    
    def replace(match):
        num = match.group(1)
        start_pos = match.start()
        end_pos = match.end()
        
        # Get context around the number (20 chars before and after)
        context_start = max(0, start_pos - 20)
        context_end = min(len(text), end_pos + 20)
        context = text[context_start:context_end].lower()
        
        # Skip if number is part of model name/version patterns:
        # - GPT-4, GPT-3.5, GPT-4o, etc.
        # - v2.0, v1.5, version 2.0, etc.
        # - 3.5-turbo, 4-turbo, etc.
        # - Any number followed by a dash and text (e.g., "model-4", "version-3.5")
        # - Any number preceded by "v" or "version" (e.g., "v2.0", "version 3.5")
        # - Any number in pattern like "X.Y" where it's clearly a version (e.g., "3.5-turbo")
        
        # Check if preceded by model name patterns
        before_context = text[max(0, start_pos - 10):start_pos].lower()
        after_context = text[end_pos:min(len(text), end_pos + 10)].lower()
        
        # Skip if it's a version number pattern
        if re.search(r'\b(v|version)\s*$', before_context):
            return num  # Don't highlight version numbers
        
        # Skip if it's part of a model name (GPT-X, model-X, etc.)
        if re.search(r'\b(gpt|model|llm|bert|roberta|t5|gpt-\d|model-\d|v\d)', before_context):
            return num  # Don't highlight model names/versions
        
        # Skip if followed by version-like patterns (e.g., "-turbo", "-base", "-large")
        if re.search(r'^[-.]\s*(turbo|base|large|small|mini|nano|pro|plus|max)', after_context):
            return num  # Don't highlight version suffixes
        
        # Skip if it's a decimal version number (e.g., "3.5" in "GPT-3.5-turbo")
        if '.' in num and re.search(r'^[-.]', after_context):
            return num  # Likely a version number like "3.5-turbo"
        
        # Otherwise, highlight it as a statistic
        return f'<span class="fancy-number-highlight" style="color: {primary_color}; font-size: 1.4em; font-weight: 700;">{num}</span>'
    
    return re.sub(pattern, replace, text)


def markdown_to_html(text: str) -> str:
    """
    Converts a subset of markdown to HTML:
    - **text** to <strong>text</strong> (bold)
    - *text* to <em>text</em> (italic)
    
    Args:
        text: Text string with markdown formatting
        
    Returns:
        Text with HTML tags replacing markdown
    """
    # Handle bold (**text**) - must be done before italic to avoid conflicts
    text = re.sub(r'\*\*([^*]+?)\*\*', r'<strong>\1</strong>', text)
    # Handle italic (*text*) - ensure it's not part of a bold marker
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', text)
    return text

