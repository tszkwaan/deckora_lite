"""
Utility functions for web slides generation.
"""

from typing import Dict, Optional


def _get_theme_colors(config: Optional[Dict]) -> Dict[str, str]:
    """Get theme colors based on scenario."""
    if not config or not isinstance(config, dict):
        return {
            "primary": "#7C3AED",
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    
    scenario = config.get("scenario", "").lower()
    
    if "academic" in scenario:
        return {
            "primary": "#1E40AF",  # Blue
            "secondary": "#3B82F6",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    elif "business" in scenario:
        return {
            "primary": "#059669",  # Green
            "secondary": "#10B981",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    else:
        return {
            "primary": "#7C3AED",  # Purple
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }

