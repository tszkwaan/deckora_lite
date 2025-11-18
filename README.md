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

**Option A: Run directly via Python**
```bash
python main.py
```

**Option B: Run via ADK-web UI** (for interactive development and debugging)

1. **Start ADK API Server** (in one terminal):
```bash
adk api_server --allow_origins=http://localhost:4200 --host=0.0.0.0
```

2. **Start ADK-web** (in another terminal, from `.project_internal/adk-web/`):
```bash
cd .project_internal/adk-web
npm run serve --backend=http://localhost:8000
```

3. **Open browser**: Go to `http://localhost:4200` and select `presentation_agent` from the dropdown

Note: The ADK API server discovers agents from your project root. Only `presentation_agent` will appear as a selectable agent in ADK-web.

## Project Structure

```
├── presentation_agent/   # Main agent app (discovered by ADK-web)
│   ├── agent.py         # Entry point: exports root_agent
│   ├── agents/          # Sub-agent implementations
│   │   ├── report_understanding_agent/
│   │   ├── outline_generator_agent/
│   │   ├── outline_critic_agent/
│   │   ├── slide_and_script_generator_agent/
│   │   ├── layout_critic_agent/
│   │   ├── tools/       # Agent tools
│   │   └── utils/       # Utility functions
│   └── output/          # Generated outputs
├── config.py            # Configuration
├── main.py              # Main script (for direct execution)
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

## Deployment

See [presentation_agent/deployment/DEPLOYMENT.md](presentation_agent/deployment/DEPLOYMENT.md) for instructions on deploying to Google Cloud Run using GitHub Actions CI/CD.

**Deployment Files**: All deployment configuration is in `presentation_agent/deployment/` folder.

Quick deployment:
1. Set up Google Cloud project and service account (see `presentation_agent/deployment/DEPLOYMENT_SETUP.md`)
2. Add secrets to GitHub repository
3. Push to `main` branch - deployment happens automatically!
4. After deployment, your API will be available at the Cloud Run URL

**API Endpoints:**
- `GET /health` - Health check
- `POST /generate` - Generate presentation

**Example API Call:**
```bash
curl -X POST https://YOUR_SERVICE_URL/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report_url": "https://arxiv.org/pdf/2511.08597",
    "scenario": "academic_teaching",
    "duration": "20 minutes",
    "target_audience": "students"
  }'
```

## Notes

- Uses `gemini-2.5-flash-lite` by default (configurable in `config.py`)
- All agents use retry configuration for API reliability
- Quality gates: Outline must pass hallucination/safety checks; slides must pass layout review
- Automatic retry: Both outline and slide generation retry up to 3 times if quality checks fail
- Google Slides export requires OAuth setup
- Layout review requires Vision API and `pdf2image`
