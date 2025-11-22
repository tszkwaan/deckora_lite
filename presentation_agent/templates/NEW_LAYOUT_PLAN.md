# New Layout Templates Plan

Based on the provided slide examples, here are the new layout templates to create:

## 1. **icon-row** (Page Layout)
**Based on:** "Why this problem?" slide

**Description:** Horizontal row of 2-4 icons, each with a label below. Clean, simple layout for showcasing features, problems, or concepts.

**Structure:**
- Title at top
- Horizontal row of icons (2-4 items)
- Each item: icon above, text label below
- Equal spacing between items
- Responsive: wraps to 2 rows if needed

**Data Structure:**
```json
{
  "layout_type": "icon-row",
  "visual_elements": {
    "icon_items": [
      {"image_keyword": "crowd", "label": "Vast amount"},
      {"image_keyword": "format", "label": "Various format"},
      {"image_keyword": "search", "label": "Lack of contextual matching"}
    ]
  }
}
```

**Use Cases:**
- Problem statements (3 problems)
- Feature highlights (2-4 features)
- Concept overviews
- Quick visual summaries

---

## 2. **icon-sequence** (Page Layout)
**Based on:** "What are we doing?" slide

**Description:** Sequence of 3+ icons arranged horizontally with connecting elements (arrows, question marks, plus signs) between them. Shows a process or relationship flow.

**Structure:**
- Title at top
- Optional subtitle/goal text
- Horizontal sequence: Icon → Connector → Icon → Connector → Icon
- Connectors can be: arrows, question marks, plus signs, equals signs, etc.
- Icons can have labels

**Data Structure:**
```json
{
  "layout_type": "icon-sequence",
  "visual_elements": {
    "sequence_items": [
      {"image_keyword": "cv", "label": "CV", "connector": "arrow"},
      {"image_keyword": "matching", "label": "Matching", "connector": "question"},
      {"image_keyword": "job", "label": "JOB", "connector": null}
    ],
    "goal_text": "Goal: Build an AI system for HR professionals..."
  }
}
```

**Use Cases:**
- Process visualization (input → process → output)
- Relationship mapping
- Workflow overviews
- Conceptual flows

---

## 3. **linear-process** (Page Layout)
**Based on:** "Inference pipeline" slide

**Description:** Linear step-by-step process with numbered steps, icons, and connecting arrows. Shows a sequential pipeline or workflow.

**Structure:**
- Title at top
- Optional section header
- Linear flow: Step 1 → Step 2 → Step 3 → ... → Step N
- Each step: number, icon, label
- Arrows between steps
- Can wrap to multiple rows if many steps

**Data Structure:**
```json
{
  "layout_type": "linear-process",
  "visual_elements": {
    "process_steps": [
      {"step_number": 1, "image_keyword": "document", "label": "Document Input"},
      {"step_number": 2, "image_keyword": "upload", "label": "Upload to Website"},
      {"step_number": 3, "image_keyword": "ocr", "label": "OCR"},
      {"step_number": 4, "image_keyword": "security", "label": "Prompt injection detection"},
      {"step_number": 5, "image_keyword": "preprocess", "label": "Text preprocess"},
      {"step_number": 6, "image_keyword": "llm", "label": "Large Language Model"},
      {"step_number": 7, "image_keyword": "evaluation", "label": "Evaluation result"},
      {"step_number": 8, "image_keyword": "factcheck", "label": "Hallucination detection"}
    ],
    "section_header": "Inference pipeline"  // Optional
  }
}
```

**Use Cases:**
- Pipeline descriptions
- Step-by-step processes
- Sequential workflows
- Linear procedures

---

## 4. **workflow-diagram** (Page Layout)
**Based on:** "LLM-as-Judge & Distillation - Step 1" slide

**Description:** Complex workflow diagram with inputs, process boxes, outputs, and connections. Shows system architecture or multi-stage processes.

**Structure:**
- Title at top
- Optional subtitle/step indicator
- Multiple input boxes
- Process boxes (rounded rectangles)
- Output boxes
- Arrows showing flow
- Can have branching/merging flows
- Optional evaluation criteria list

**Data Structure:**
```json
{
  "layout_type": "workflow-diagram",
  "visual_elements": {
    "workflow": {
      "inputs": [
        {"type": "document", "label": "JOB", "image_keyword": "job"},
        {"type": "document", "label": "CV", "image_keyword": "cv"}
      ],
      "processes": [
        {"id": "llm_judge", "label": "Powerful Close-source Model", "type": "llm"}
      ],
      "outputs": [
        {"id": "recommendation", "label": "Hiring Recommendation*", "note": "match percentage 100%, 80%, 60%, 50%, and 10%"}
      ],
      "connections": [
        {"from": "input_0", "to": "llm_judge"},
        {"from": "input_1", "to": "llm_judge"},
        {"from": "llm_judge", "to": "recommendation"}
      ],
      "evaluation_criteria": [  // Optional
        "Relevant_Skills",
        "Experience Relevance",
        "Position Fit",
        "Capability",
        "Bonus Points",
        "Deductions",
        "Strengths"
      ]
    }
  }
}
```

**Use Cases:**
- System architecture
- Multi-stage processes
- Complex workflows
- Training pipelines
- Evaluation systems

---

## 5. **process-flow** (Page Layout)
**Based on:** "Training pipeline" / "Overall Architecture" slide

**Description:** Flowchart-style process with multiple stages, branching, and merging. More flexible than linear-process, supports parallel paths.

**Structure:**
- Title at top
- Optional section header
- Flowchart with boxes and arrows
- Can have parallel branches
- Can have merging points
- Each box: icon + label

**Data Structure:**
```json
{
  "layout_type": "process-flow",
  "visual_elements": {
    "flow_stages": [
      {
        "stage": 1,
        "title": "LLM as judge",
        "inputs": [
          {"type": "document", "label": "JOB", "image_keyword": "job"},
          {"type": "document", "label": "CV", "image_keyword": "cv"}
        ],
        "process": {"label": "LLM", "image_keyword": "llm"},
        "output": {"label": "Evaluation", "image_keyword": "clipboard"}
      },
      {
        "stage": 2,
        "title": "Distillation",
        "inputs": [
          {"type": "document", "label": "JOB", "image_keyword": "job"},
          {"type": "document", "label": "CV", "image_keyword": "cv"},
          {"type": "output", "label": "Evaluation", "from_stage": 1}
        ],
        "process": {"label": "Lighter LM", "image_keyword": "model"},
        "output": {"label": "Optimized Model", "image_keyword": "model"}
      }
    ],
    "section_header": "Training pipeline"  // Optional
  }
}
```

**Use Cases:**
- Training pipelines
- Multi-stage processes
- Architecture diagrams
- Complex workflows with branching

---

## Implementation Plan

### Phase 1: Remove Image Limit
1. Remove `if len(image_items) >= 3:` checks from `web_slides_generator_tool.py` (4 locations)
2. Update comments to reflect unlimited images

### Phase 2: Create New Components
1. **icon-item** component (for icon-row)
   - Icon above, label below
   - Responsive sizing

2. **sequence-connector** component (for icon-sequence)
   - Arrow, question mark, plus, equals, etc.
   - Stylized connectors

3. **process-step** component (for linear-process)
   - Numbered step
   - Icon + label
   - Arrow connector

4. **workflow-box** component (for workflow-diagram)
   - Input/output/process boxes
   - Rounded rectangles
   - Labels

### Phase 3: Create New Page Layouts
1. **icon-row.json** - Horizontal row of icons
2. **icon-sequence.json** - Sequence with connectors
3. **linear-process.json** - Step-by-step pipeline
4. **workflow-diagram.json** - Complex workflow
5. **process-flow.json** - Flowchart-style process

### Phase 4: Update Template Helpers
1. `render_icon_row_html()` - Render icon-row layout
2. `render_icon_sequence_html()` - Render icon-sequence layout
3. `render_linear_process_html()` - Render linear-process layout
4. `render_workflow_diagram_html()` - Render workflow-diagram layout
5. `render_process_flow_html()` - Render process-flow layout

### Phase 5: Update Agent Instructions
1. Add new layout types to `layout_type` options
2. Add examples of when to use each layout
3. Update visual-first design guidance

### Phase 6: Update Web Slides Generator
1. Add layout type handling for new layouts
2. Call appropriate render functions
3. Test with sample data

---

## Design Considerations for 1200px × 500px

All new layouts must account for:
- **Width:** 1200px (wider canvas - can fit more horizontal elements)
- **Height:** 500px (shorter - need efficient vertical spacing)
- **Padding:** 40-60px horizontal, 30-40px vertical
- **Content area:** ~1080-1120px × ~420-440px
- **Icon sizes:** 80-120px for small icons, 150-250px for medium
- **Font sizes:** Title 28-36pt, labels 12-16pt
- **Spacing:** Tighter vertical spacing (6-10% gaps)

---

## Priority Order

1. **icon-row** (simplest, most commonly needed)
2. **icon-sequence** (useful for process visualization)
3. **linear-process** (common for pipelines)
4. **workflow-diagram** (complex but powerful)
5. **process-flow** (most complex, least common)

---

## Notes

- All layouts should support unlimited images (remove 3-image limit)
- Icons should use `image_keyword` to generate images on-the-fly
- Layouts should be responsive and work well at 1200px × 500px
- Keep visual-first design principle - minimize text, maximize visuals
- Use Mermaid for complex flowcharts if needed (already integrated)

