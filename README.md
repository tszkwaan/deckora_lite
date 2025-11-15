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
│   ├── style_extractor.py
│   ├── outline_generator.py
│   ├── slide_generator.py
│   ├── script_generator.py
│   ├── critic.py
│   └── orchestrator.py
├── utils/               # Utility functions
├── config.py            # Configuration
├── main.py              # Main script
└── requirements.txt     # Dependencies
```

## Pipeline Overview

1. **Report Understanding Agent**: Transforms raw report text into structured knowledge
2. **Outline Generator Agent**: Creates presentation outline based on report knowledge
3. **Slide Generator Agent**: Generates detailed slide content
4. **Script Generator Agent**: Creates detailed presentation script
5. **Critic Agents**: Review quality at each stage

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
- `complete_output.json` - All outputs combined

## Notes

- Uses `gemini-2.5-flash-lite` by default (configurable in `config.py`)
- All agents use retry configuration for API reliability
- Intermediate outputs are saved for debugging
- Critic agents can be disabled for faster execution
