# Presentation AI - Deckora Lite

A multi-agent system for generating presentations from research reports using Google's ADK (Agent Development Kit).

## Quick Start

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Set API Key
```bash
export GOOGLE_API_KEY='your-api-key-here'
```
Or create a `.env` file: `GOOGLE_API_KEY=your-api-key-here`

### 3. Run Pipeline
```bash
python main.py
```

## Project Structure

```
├── agents/              # Agent implementations
│   ├── report_understanding.py
│   ├── outline_generator.py
│   ├── slide_and_script_generator.py
│   ├── critic.py
│   ├── slideshow_exporter.py
│   ├── layout_critic.py
│   └── orchestrator.py
├── tools/               # Agent tools
│   ├── google_slides_tool.py
│   └── google_slides_layout_tool.py
├── utils/               # Utility functions
│   ├── helpers.py
│   ├── pdf_loader.py
│   └── quality_check.py
├── config.py            # Configuration
├── main.py              # Main script
└── requirements.txt     # Dependencies
```

## Multi-Agent Workflow

The pipeline uses a sequential multi-agent system with quality gates:

1. **Report Understanding Agent**: Extracts structured knowledge from PDF report
2. **Outline Generator Agent**: Creates presentation outline from report knowledge
3. **Outline Critic Agent**: Reviews outline quality (hallucination & safety checks)
   - Retry loop: Regenerates outline if quality check fails (max 3 attempts)
4. **Slide and Script Generator Agent**: Generates both detailed slide content and presentation script together
5. **Google Slides Exporter Agent**: Exports slides and script to Google Slides
7. **Layout Critic Agent**: Reviews slide layout for text overlap issues using Vision API
   - Retry loop: Regenerates slides if layout issues found (max 3 attempts)
   - Passes only if no text overlap detected

## Configuration

Edit `main.py` to customize:

```python
config = PresentationConfig(
    scenario="academic_teaching",  # or "business_pitch", "technical_demo"
    duration="20 minutes",
    target_audience="students",  # or "C-level", "colleagues", "non-technical"
    custom_instruction="keep slides clean, point form only",
    report_url="https://arxiv.org/pdf/2511.08597",
    style_images=[],  # List of image URLs for style extraction
)
```

## Outputs

Generated files in `output/` directory:
- `report_knowledge.json` - Structured knowledge extracted from report
- `presentation_outline.json` - Presentation outline
- `outline_review.json` - Outline quality review
- `slide_deck.json` - Generated slide content
- `presentation_script.json` - Presentation script with timing
- `presentation_slides_id.txt` - Google Slides presentation ID
- `presentation_slides_url.txt` - Shareable Google Slides URL
- `layout_review.json` - Layout review results (if Vision API configured)
- `complete_output.json` - All outputs combined

## Notes

- Uses `gemini-2.5-flash-lite` by default (configurable in `config.py`)
- All agents use retry configuration for API reliability
- Quality gates: Outline must pass hallucination/safety checks; slides must pass layout review
- Automatic retry: Both outline and slide generation retry up to 3 times if quality checks fail
- Google Slides export requires OAuth setup
- Layout review requires Vision API and `pdf2image`
