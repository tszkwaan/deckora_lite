"""
Template loader for slide layouts and components.
Loads template JSON files and provides rendering functionality.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger(__name__)

# Template directory (now in utils, need to go up one level to find templates)
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
PAGE_LAYOUTS_DIR = TEMPLATES_DIR / "page_layouts"
COMPONENTS_DIR = TEMPLATES_DIR / "components"


class TemplateLoader:
    """Loads and manages template files."""
    
    def __init__(self):
        self._template_cache: Dict[str, Dict] = {}
        self._load_all_templates()
    
    def _load_all_templates(self):
        """Pre-load all templates into cache."""
        # Load page layouts
        if PAGE_LAYOUTS_DIR.exists():
            for template_file in PAGE_LAYOUTS_DIR.glob("*.json"):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template = json.load(f)
                        template_name = template.get('name', template_file.stem)
                        self._template_cache[f"page_layout:{template_name}"] = template
                        logger.debug(f"Loaded page layout template: {template_name}")
                except Exception as e:
                    logger.error(f"Failed to load template {template_file}: {e}")
        
        # Load components
        if COMPONENTS_DIR.exists():
            for template_file in COMPONENTS_DIR.glob("*.json"):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template = json.load(f)
                        template_name = template.get('name', template_file.stem)
                        self._template_cache[f"component:{template_name}"] = template
                        logger.debug(f"Loaded component template: {template_name}")
                except Exception as e:
                    logger.error(f"Failed to load template {template_file}: {e}")
    
    def get_template(self, template_type: str, template_name: str) -> Optional[Dict]:
        """Get a template by type and name."""
        key = f"{template_type}:{template_name}"
        return self._template_cache.get(key)
    
    def get_page_layout(self, layout_name: str) -> Optional[Dict]:
        """Get a page layout template."""
        return self.get_template("page_layout", layout_name)
    
    def get_component(self, component_name: str) -> Optional[Dict]:
        """Get a component template."""
        return self.get_template("component", component_name)
    
    def list_available_layouts(self) -> List[str]:
        """List all available page layout names."""
        return [
            key.replace("page_layout:", "")
            for key in self._template_cache.keys()
            if key.startswith("page_layout:")
        ]
    
    def list_available_components(self) -> List[str]:
        """List all available component names."""
        return [
            key.replace("component:", "")
            for key in self._template_cache.keys()
            if key.startswith("component:")
        ]


def render_template(template: Dict, variables: Dict[str, Any], theme_colors: Optional[Dict] = None, component_renderer=None) -> str:
    """
    Render a template with provided variables.
    
    Args:
        template: Template dict with 'html' and optionally 'css'
        variables: Dict of variable values to inject
        theme_colors: Optional theme colors dict
        component_renderer: Optional function to render nested components
        
    Returns:
        Rendered HTML string
    """
    html = template.get('html', '')
    css = template.get('css', '')
    
    # Merge theme colors into variables if provided
    if theme_colors:
        variables = {**variables, **{f"theme_{k}": v for k, v in theme_colors.items()}}
    
    # Replace variables in HTML: {variable_name} or {variable_name|default}
    def replace_var(match):
        var_expr = match.group(1)
        if '|' in var_expr:
            var_name, default = var_expr.split('|', 1)
            default = default.strip()
        else:
            var_name = var_expr
            default = ''
        
        var_name = var_name.strip()
        value = variables.get(var_name, default)
        
        # Handle None values
        if value is None:
            return default or ''
        
        # Handle list/array - render as HTML if it's an array of objects/dicts
        if isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], dict):
                # Array of objects - render as component instances
                if component_renderer:
                    rendered_items = []
                    for item in value:
                        # Try to render as component if component_renderer is available
                        rendered_items.append(component_renderer(item))
                    return '\n'.join(rendered_items)
            # Simple array - join with newlines
            return '\n'.join(str(v) for v in value)
        
        return str(value)
    
    # Replace {variable} patterns, but be careful not to match CSS braces
    # Use a more specific pattern that only matches template variables (not CSS braces)
    # Pattern: {variable_name} where variable_name doesn't contain braces
    html = re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_|]*)\}', replace_var, html)
    
    # If CSS is provided, wrap in <style> tag
    if css:
        # For CSS, we need to replace theme variables but preserve CSS structure
        # Replace theme variables: {theme_primary}, {theme_text}, etc.
        css_rendered = re.sub(r'\{theme_([a-zA-Z_][a-zA-Z0-9_]*)\}', 
                             lambda m: variables.get(f"theme_{m.group(1)}", ""), css)
        # Replace other template variables in CSS (but not CSS braces)
        css_rendered = re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_|]*)\}', replace_var, css_rendered)
        html = f"<style>{css_rendered}</style>\n{html}"
    
    return html


def render_component(component_name: str, variables: Dict[str, Any], theme_colors: Optional[Dict] = None) -> str:
    """
    Render a component by name.
    
    Args:
        component_name: Name of the component
        variables: Variables to inject
        theme_colors: Optional theme colors
        
    Returns:
        Rendered HTML string
    """
    # Use singleton instance to avoid reloading
    if not hasattr(render_component, '_loader'):
        render_component._loader = TemplateLoader()
    
    component = render_component._loader.get_component(component_name)
    
    if not component:
        logger.warning(f"Component '{component_name}' not found, returning empty string")
        return ""
    
    return render_template(component, variables, theme_colors)


def render_page_layout(layout_name: str, variables: Dict[str, Any], theme_colors: Optional[Dict] = None) -> str:
    """
    Render a page layout by name.
    
    Args:
        layout_name: Name of the layout
        variables: Variables to inject
        theme_colors: Optional theme colors
        
    Returns:
        Rendered HTML string
    """
    # Use singleton instance to avoid reloading
    if not hasattr(render_page_layout, '_loader'):
        render_page_layout._loader = TemplateLoader()
    
    layout = render_page_layout._loader.get_page_layout(layout_name)
    
    if not layout:
        logger.warning(f"Page layout '{layout_name}' not found, falling back to default")
        # Fallback to basic layout
        return f'<div class="slide-content"><h1 class="slide-title">{variables.get("title", "")}</h1><div class="slide-body">{variables.get("content", "")}</div></div>'
    
    return render_template(layout, variables, theme_colors)

