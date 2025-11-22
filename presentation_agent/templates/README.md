# Template System Documentation

## Overview

The template system provides reusable page layouts and components for generating presentation slides. Templates are stored as JSON files and can be easily customized or extended.

## Directory Structure

```
templates/
├── page_layouts/          # Overall slide structure templates
│   ├── comparison-grid.json
│   ├── data-table.json
│   └── timeline.json
├── components/            # Reusable component templates
│   ├── comparison-section.json
│   ├── data-table.json
│   ├── flowchart.json
│   ├── timeline-item.json
│   └── icon-feature-card.json
├── template_loader.py    # Template loading and caching
├── template_helpers.py   # Helper functions for rendering
└── README.md             # This file
```

## Available Templates

### Page Layouts

#### 1. `comparison-grid`
**Purpose**: Dynamic grid layout for comparing 2-4 items side-by-side

**When to use**: Comparing multiple items/concepts (models, methods, scenarios)

**Configuration**:
- `sections`: Array of 2-4 section objects
- Auto-adjusts: 1x2 grid (2 sections), 2x2 grid (3-4 sections)

**Example**:
```json
{
  "layout_type": "comparison-grid",
  "visual_elements": {
    "sections": [
      {"title": "GPT-3.5 Automated", "content": "92% success rate"},
      {"title": "GPT-3.5 Human", "content": "21% success rate"},
      {"title": "LLaMA3 Automated", "content": "78% success rate"},
      {"title": "LLaMA3 Human", "content": "18% success rate"}
    ]
  }
}
```

#### 2. `data-table`
**Purpose**: Generic table layout for displaying structured data

**When to use**: Tabular data, comparisons, metrics, results

**Configuration**:
- `table_data.headers`: Array of header objects `[{"text": "Model", "width": "30%"}, ...]`
- `table_data.rows`: Array of row arrays `[["GPT-3.5", "21%", "92%"], ...]`
- `table_data.style`: "default" | "striped" | "bordered" | "minimal"
- `table_data.highlight_rows`: Optional row indices to highlight
- `table_data.highlight_columns`: Optional column indices to highlight

**Example**:
```json
{
  "layout_type": "data-table",
  "visual_elements": {
    "table_data": {
      "headers": [
        {"text": "Model", "width": "30%"},
        {"text": "Human Eval", "width": "35%"},
        {"text": "Automated Eval", "width": "35%"}
      ],
      "rows": [
        ["GPT-3.5 Zero-shot", "21%", "92%"],
        ["LLaMA3 Zero-shot", "18%", "78%"]
      ],
      "style": "striped",
      "highlight_columns": [1, 2]
    }
  }
}
```

#### 3. `timeline`
**Purpose**: Timeline layout for showing progression, roadmap, or chronological flow

**When to use**: Steps, phases, chronological sequences

**Configuration**:
- `timeline_items`: Array of timeline item objects
- `timeline_orientation`: "vertical" (default) | "horizontal"

**Example**:
```json
{
  "layout_type": "timeline",
  "visual_elements": {
    "timeline_items": [
      {"year": "Step 1", "title": "Generate MHQ", "description": "Create mitigated harmful queries"},
      {"year": "Step 2", "title": "Test Models", "description": "Evaluate on multiple models"}
    ]
  }
}
```

### Components

#### 1. `comparison-section`
Used by `comparison-grid` layout. Single section in a comparison grid.

**Variables**: `title`, `content`, `icon`, `icon_url`, `background_color`, `highlight`

#### 2. `data-table`
Generic table component (can be used standalone or in `data-table` layout).

**Variables**: `headers`, `rows`, `style`, `highlight_rows`, `highlight_columns`, `caption`

#### 3. `flowchart`
Simple flowchart/process diagram.

**Variables**: `steps` (array of `{label, description}`), `orientation`, `style`

#### 4. `timeline-item`
Single item in a timeline (used by `timeline` layout).

**Variables**: `year`, `title`, `description`, `icon`, `highlight`

#### 5. `icon-feature-card`
Feature/item card with icon, title, and description.

**Variables**: `icon`, `icon_url`, `title`, `description`, `highlight`

## Usage in Slide Generator

### Selecting Layout Type

In `design_spec`, set `layout_type`:

```json
{
  "design_spec": {
    "layout_type": "comparison-grid",
    "title_font_size": 36,
    ...
  }
}
```

### Providing Template Data

For `comparison-grid`:
```json
{
  "visual_elements": {
    "sections": [
      {"title": "Section 1", "content": "...", "icon": "..."},
      {"title": "Section 2", "content": "...", "icon": "..."}
    ]
  }
}
```

For `data-table`:
```json
{
  "visual_elements": {
    "table_data": {
      "headers": [{"text": "Column 1"}, {"text": "Column 2"}],
      "rows": [["Row 1 Col 1", "Row 1 Col 2"], ["Row 2 Col 1", "Row 2 Col 2"]],
      "style": "striped"
    }
  }
}
```

For `timeline`:
```json
{
  "visual_elements": {
    "timeline_items": [
      {"year": "2024", "title": "Phase 1", "description": "..."},
      {"year": "2025", "title": "Phase 2", "description": "..."}
    ]
  }
}
```

## Adding New Templates

1. Create a JSON file in `page_layouts/` or `components/`
2. Follow the template structure:
   ```json
   {
     "name": "template-name",
     "type": "page_layout" | "component",
     "description": "...",
     "variables": {
       "var_name": {
         "type": "string" | "array" | "number" | "boolean" | "object",
         "required": true | false,
         "description": "..."
       }
     },
     "html": "<div>{variable}</div>",
     "css": ".class { color: {theme_primary}; }",
     "usage_examples": [...]
   }
   ```
3. Templates are auto-loaded on startup
4. Use `{variable_name}` for placeholders
5. Use `{variable_name|default_value}` for optional variables
6. Theme colors are auto-injected as `{theme_primary}`, `{theme_secondary}`, etc.

## Template Variables

- `{variable}` - Required variable
- `{variable|default}` - Optional variable with default value
- `{theme_primary}` - Primary theme color (auto-injected)
- `{theme_secondary}` - Secondary theme color (auto-injected)
- `{theme_background}` - Background color (auto-injected)
- `{theme_text}` - Text color (auto-injected)

## Helper Functions

Use helper functions from `template_helpers.py` for complex rendering:

- `render_comparison_grid_html()` - Render comparison grid with sections
- `render_data_table_html()` - Render data table
- `render_flowchart_html()` - Render flowchart
- `render_timeline_html()` - Render timeline
- `render_icon_feature_card_html()` - Render feature card

These handle conditional logic, array processing, and component composition automatically.

