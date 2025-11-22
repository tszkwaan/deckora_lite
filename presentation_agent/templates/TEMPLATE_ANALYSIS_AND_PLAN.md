# Template System Analysis & Implementation Plan

## 📊 Current Slide Analysis (from Self-HarmLLM report)

### Existing Slide Patterns:

1. **Slide 1: Cover Slide**
   - Type: Title + Subtitle only
   - Layout: Centered, minimal
   - Content: Title + subtitle text
   - Current template: `slide-text-only` (centered)

2. **Slide 2: Concept Introduction**
   - Type: Text content with bullet points
   - Layout: Title + bullet list
   - Content: 3 bullet points explaining concept
   - Icons suggested: shield, lock, bug
   - Current template: `slide-text-only` (left-aligned)

3. **Slide 3: Experimental Results**
   - Type: Content + Chart
   - Layout: Title + bullets (left) + Bar chart (right)
   - Content: 3 bullets + bar chart with 6 data points
   - Current template: `slide-with-chart` (2-column grid)

4. **Slide 4: Comparison Analysis**
   - Type: Content + Comparison Chart
   - Layout: Title + bullets (left) + Comparison bar chart (right)
   - Content: 3 bullets + comparison chart (Automated vs Human)
   - Current template: `slide-with-chart` (2-column grid)

5. **Slide 5: Conclusion**
   - Type: Summary/Conclusion
   - Layout: Title + bullet list
   - Content: 4 bullet points summarizing takeaways
   - Icons suggested: lightbulb, arrow-up, magnifying-glass
   - Current template: `slide-text-only` (left-aligned)

---

## 🎯 Identified Needs & Opportunities

### Missing Layout Patterns:
1. **Multi-section comparison slides** (like the 4-section grid in your reference image)
2. **Metric/stat cards** (for highlighting key numbers)
3. **Timeline layouts** (for showing progression/roadmap)
4. **Testimonial/quote layouts** (for social proof)
5. **Icon-enhanced sections** (currently icons are just decorative)
6. **Multi-column text layouts** (for comparing concepts side-by-side)

### Content Types Observed:
- ✅ Title + Subtitle (cover)
- ✅ Title + Bullet points (content)
- ✅ Title + Bullets + Chart (data visualization)
- ❌ Title + Metrics/Stats (highlighting numbers)
- ❌ Title + Comparison sections (4-way comparison)
- ❌ Title + Timeline (progression)
- ❌ Title + Quote/Testimonial (social proof)
- ❌ Title + Icon cards (feature highlights)

---

## 📋 Proposed Template Structure

### Phase 1: Page Layout Templates

#### 1.1 `cover-slide` (✅ Already exists, needs refinement)
**Purpose**: First slide with title and subtitle
**When to use**: slide_number = 1
**Structure**:
```
[Title - Centered, Large]
[Subtitle - Centered, Medium]
```

#### 1.2 `content-text` (✅ Already exists)
**Purpose**: Standard content slide with title and bullet points
**When to use**: Text-only content, no charts
**Structure**:
```
[Title - Left/Center]
[Bullet Points - Left]
```

#### 1.3 `content-with-chart` (✅ Already exists)
**Purpose**: Content + chart side-by-side
**When to use**: When charts_needed = true
**Structure**:
```
[Title - Full width]
[Content (left) | Chart (right)]
```

#### 1.4 `comparison-grid` (🆕 NEW - High Priority)
**Purpose**: Dynamic grid layout for comparing 2-4 items/concepts side-by-side
**When to use**: Comparing multiple items/concepts
**Structure** (Dynamic based on number of sections):
```
[Title - Full width]
[Section 1 | Section 2]                    # 2 sections: 1x2 grid
[Section 1 | Section 2]                    # 3 sections: 2x2 grid (1 empty)
[Section 3 | Section 4]                    # 4 sections: 2x2 grid
```
**Configuration**:
- `sections_count`: 2, 3, or 4 (minimum 2)
- Auto-adjusts grid: 1x2 (2 sections), 2x2 (3-4 sections)
- Each section uses `comparison-section` component

**Use cases from report**:
- Comparing models (GPT-3.5 vs LLaMA3 vs DeepSeek)
- Comparing evaluation methods (Automated vs Human)
- Comparing mitigation strategies (Zero-shot vs Few-shot)

#### 1.5 `data-table` (🆕 NEW - High Priority)
**Purpose**: Generic table layout for displaying structured data/metrics
**When to use**: Tabular data, comparisons, metrics, results
**Structure**:
```
[Title - Full width]
[Table with headers and rows]
[Optional: Summary text below]
```
**Configuration**:
- `columns`: Array of column definitions (header, width, alignment)
- `rows`: Array of row data
- `highlight_rows`: Optional row highlighting
- `highlight_columns`: Optional column highlighting

**Use cases from report**:
- Model comparison table (GPT-3.5, LLaMA3, DeepSeek with their metrics)
- Evaluation results table (Automated vs Human for each model)
- Success rates table (Zero-shot, Few-shot, Base conditions)

#### 1.6 `timeline` (🆕 NEW - Medium Priority)
**Purpose**: Show progression, roadmap, or chronological flow
**When to use**: Showing steps, phases, or timeline
**Structure**:
```
[Title - Full width]
[Timeline Item 1 → Timeline Item 2 → Timeline Item 3]
```
**Use cases from report**:
- Experimental setup process
- Evaluation methodology steps
- Future research phases

#### 1.7 `testimonial-quote` (🆕 NEW - Low Priority)
**Purpose**: Highlight quote or testimonial
**When to use**: Social proof, key quote, expert opinion
**Structure**:
```
[Title - Full width]
[Large Quote Text]
[Attribution]
[Optional: Image/Icon]
```

---

### Phase 2: Component Templates

#### 2.1 `comparison-section` (🆕 NEW - High Priority)
**Purpose**: Single section in a comparison grid layout
**Template variables**: `{title}`, `{content}`, `{icon}`, `{background_color}`, `{highlight}`
**Example**:
```html
<div class="comparison-section">
  <div class="section-icon">{icon}</div>
  <h3 class="section-title">{title}</h3>
  <div class="section-content">{content}</div>
</div>
```
**Use cases**:
- "GPT-3.5 Zero-shot" section
- "LLaMA3 Few-shot" section
- "Automated Evaluation" vs "Human Evaluation"

#### 2.2 `data-table` (🆕 NEW - High Priority)
**Purpose**: Generic table component for structured data
**Template variables**: `{headers}`, `{rows}`, `{highlight_rows}`, `{highlight_columns}`, `{style}`
**Example**:
```html
<table class="data-table">
  <thead>
    <tr>{headers}</tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
```
**Use cases**:
- Model comparison table
- Evaluation results table
- Success rates by condition
- Any tabular data presentation

#### 2.3 `flowchart` (🆕 NEW - High Priority)
**Purpose**: Simple flowchart/process diagram
**Template variables**: `{steps}`, `{connections}`, `{style}`, `{orientation}`
**Example**:
```html
<div class="flowchart">
  <div class="flow-step">{step1}</div>
  <div class="flow-arrow">→</div>
  <div class="flow-step">{step2}</div>
  <div class="flow-arrow">→</div>
  <div class="flow-step">{step3}</div>
</div>
```
**Use cases**:
- Experimental setup process
- Evaluation methodology flow
- Attack vector flow (MHQ generation → Bypass)
- Any sequential process

#### 2.4 `timeline-item` (🆕 NEW - Medium Priority)
**Purpose**: Single item in a timeline
**Template variables**: `{year/step}`, `{title}`, `{description}`, `{icon}`
**Example**:
```html
<div class="timeline-item">
  <div class="timeline-marker">{year}</div>
  <div class="timeline-content">
    <h4>{title}</h4>
    <p>{description}</p>
  </div>
</div>
```

#### 2.5 `quote-block` (🆕 NEW - Low Priority)
**Purpose**: Display a quote or testimonial
**Template variables**: `{quote_text}`, `{attribution}`, `{image_url}`
**Example**:
```html
<div class="quote-block">
  <div class="quote-icon">"</div>
  <div class="quote-text">{quote_text}</div>
  <div class="quote-attribution">{attribution}</div>
</div>
```

#### 2.6 `icon-feature-card` (🆕 NEW - Medium Priority)
**Purpose**: Feature/item with icon, title, and description
**Template variables**: `{icon}`, `{title}`, `{description}`, `{highlight}`
**Example**:
```html
<div class="icon-feature-card">
  <img src="{icon_url}" class="feature-icon" />
  <h4 class="feature-title">{title}</h4>
  <p class="feature-description">{description}</p>
</div>
```
**Use cases**:
- "Shield" icon + "Safety Guardrails" + description
- "Bug" icon + "Vulnerability" + description

---

## 🗂️ File Structure Plan

```
presentation_agent/templates/
├── __init__.py
├── template_loader.py          # Load templates from files
├── page_layouts/               # Page-level templates
│   ├── cover-slide.html
│   ├── content-text.html
│   ├── content-with-chart.html
│   ├── comparison-grid.html    # NEW - Dynamic 2-4 sections
│   ├── data-table.html         # NEW - Generic table layout
│   ├── timeline.html           # NEW
│   └── testimonial-quote.html  # NEW
├── components/                 # Reusable component templates
│   ├── comparison-section.html # NEW - For comparison-grid
│   ├── data-table.html         # NEW - Generic table component
│   ├── flowchart.html          # NEW - Process flow diagram
│   ├── timeline-item.html      # NEW
│   ├── quote-block.html        # NEW
│   └── icon-feature-card.html  # NEW
└── styles/                     # Component-specific CSS
    ├── comparison-section.css
    ├── data-table.css
    ├── flowchart.css
    ├── timeline-item.css
    └── ...
```

---

## 📝 Template File Format

Each template file will be a JSON file with this structure:

```json
{
  "name": "data-table",
  "type": "component",
  "description": "Generic table for displaying structured data",
  "variables": {
    "headers": {
      "type": "array",
      "required": true,
      "description": "Array of column headers: [{'text': 'Model', 'width': '30%'}, ...]"
    },
    "rows": {
      "type": "array",
      "required": true,
      "description": "Array of row data: [['GPT-3.5', '21%', '92%'], ...]"
    },
    "highlight_rows": {
      "type": "array",
      "required": false,
      "description": "Row indices to highlight: [0, 2]"
    },
    "highlight_columns": {
      "type": "array",
      "required": false,
      "description": "Column indices to highlight: [1, 2]"
    },
    "style": {
      "type": "string",
      "required": false,
      "default": "default",
      "description": "Table style: 'default', 'striped', 'bordered', 'minimal'"
    }
  },
  "html": "<table class=\"data-table data-table-{style}\">...</table>",
  "css": ".data-table { ... }",
  "usage_examples": [
    {
      "scenario": "Model comparison table",
      "variables": {
        "headers": [
          {"text": "Model", "width": "30%"},
          {"text": "Human Eval", "width": "35%"},
          {"text": "Automated Eval", "width": "35%"}
        ],
        "rows": [
          ["GPT-3.5 Zero-shot", "21%", "92%"],
          ["LLaMA3 Zero-shot", "18%", "78%"],
          ["DeepSeek Base", "30%", "70%"]
        ],
        "highlight_columns": [1, 2]
      }
    }
  ]
}
```

---

## 🎯 Implementation Priority

### Phase 1: High Priority (Build First)
1. ✅ **comparison-grid** page layout (Dynamic 2-4 sections)
   - **Why**: Most versatile, can handle 2-4 section comparisons
   - **Use case**: Slide 4 could use this to compare all evaluation scenarios
   - **Features**: Auto-adjusts grid layout based on section count (min 2)
   
2. ✅ **data-table** page layout + component
   - **Why**: Generic, common presentation element for structured data
   - **Use case**: Model comparison tables, evaluation results, metrics display
   - **Features**: Supports highlighting, multiple styles, flexible columns
   
3. ✅ **comparison-section** component
   - **Why**: Core component for comparison-grid layout
   - **Use case**: Each section in comparison-grid (2-4 sections)
   - **Features**: Icon, title, content, optional background color
   
4. ✅ **flowchart** component
   - **Why**: Common visualization for processes, methodologies
   - **Use case**: Experimental setup flow, attack vector flow, evaluation steps
   - **Features**: Horizontal/vertical orientation, customizable steps

### Phase 2: Medium Priority
5. **timeline** page layout
6. **timeline-item** component
7. **icon-feature-card** component

### Phase 3: Low Priority
8. **testimonial-quote** page layout
9. **quote-block** component

---

## 🔄 Integration Points

### Where templates will be used:

1. **Slide Generator Agent** (`slide_and_script_generator_agent/instructions.md`)
   - Add `layout_type` field to `design_spec`
   - Agent selects appropriate layout based on content
   - Agent specifies which components to use

2. **Web Slides Generator** (`web_slides_generator_tool.py`)
   - `_generate_slide_html_fragment()` function
   - Load template based on `layout_type`
   - Render components based on slide content
   - Inject variables into template HTML

3. **Template Loader** (`templates/template_loader.py`)
   - Load template files from disk
   - Cache templates for performance
   - Validate template structure
   - Provide template metadata to agents

---

## 📊 Expected Slide Improvements

### Current Slide 4 → Enhanced with comparison-grid:
**Before**: Title + bullets (left) + chart (right)
**After**: 
```
Title: "Evaluation Discrepancy: Automated vs. Human"
[GPT-3.5 Automated | GPT-3.5 Human]
[LLaMA3 Automated | LLaMA3 Human]
[Chart showing comparison below]
```

### Current Slide 3 → Enhanced with data-table:
**Before**: Title + bullets + chart
**After**:
```
Title: "Experimental Setup & Key Findings"
[Table: Model | Zero-shot | Few-shot | Base]
[Chart showing all data]
[Bullet points below]
```

### New Use Case: Flowchart for Experimental Process:
```
Title: "Self-HarmLLM Attack Flow"
[Flowchart: Generate MHQ → Feed to Model → Bypass Guardrails → Success]
```

---

## ✅ Next Steps

1. **Create template file structure** (directories)
2. **Design and code first 4 templates** (Phase 1)
3. **Update template loader** to read JSON template files
4. **Update web slides generator** to use templates
5. **Update slide generator instructions** to select templates
6. **Test with current report** to verify templates work
7. **Iterate based on results**

---

## 🔄 Revised Approach Summary

### Key Changes Based on Feedback:

1. **Dynamic Comparison Grid** (2-4 sections, minimum 2)
   - Auto-adjusts layout: 1x2 grid for 2 sections, 2x2 grid for 3-4 sections
   - More flexible than fixed 4-section layout

2. **Generic Data Table** (replaces metrics-dashboard)
   - More versatile - can display any tabular data
   - Supports highlighting, multiple styles
   - Common presentation element

3. **Flowchart Component** (new addition)
   - Simple process flow visualization
   - Horizontal/vertical orientation
   - Common presentation element

4. **Focus on Generic Components**
   - Table, flowchart, comparison-section
   - Reusable across different contexts
   - Standard presentation visualization elements

### Final Phase 1 Priority List:

1. **comparison-grid** (dynamic 2-4 sections) - Page Layout
2. **data-table** (generic table) - Page Layout + Component
3. **comparison-section** - Component (for comparison-grid)
4. **flowchart** - Component (for process flows)

---

## 🎨 Design Considerations

- **Consistency**: All templates should use same color scheme (from theme_colors)
- **Responsive**: Templates should work on different screen sizes
- **Accessibility**: Proper semantic HTML, ARIA labels where needed
- **Flexibility**: Templates should handle missing optional variables gracefully
- **Performance**: Template HTML should be lightweight, CSS should be efficient

