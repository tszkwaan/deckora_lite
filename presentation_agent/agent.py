from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models.google_llm import Gemini
import sys
import os
import json

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL

# Import sub-agents from agents/ subdirectory (they export 'agent', not 'root_agent')
from presentation_agent.agents.report_understanding_agent.agent import agent as report_understanding_agent
from presentation_agent.agents.outline_generator_agent.agent import agent as outline_generator_agent
from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_and_script_generator_agent
# Note: SlidesExportAgent removed - we no longer export to Google Slides, main pipeline uses web slides instead

# Import PDF loader utility
from presentation_agent.utils.pdf_loader import load_pdf_from_url


def load_pdf_from_url_tool(url: str) -> str:
    """
    Tool function to load PDF content from a URL.
    
    Args:
        url: URL to the PDF file (e.g., "https://arxiv.org/pdf/2511.08597")
        
    Returns:
        Extracted text content from all pages of the PDF
    """
    try:
        content = load_pdf_from_url(url)
        return f"Successfully loaded PDF from {url}. Content length: {len(content)} characters.\n\n[REPORT_CONTENT]\n{content}\n[END_REPORT_CONTENT]"
    except Exception as e:
        return f"Error loading PDF from {url}: {str(e)}"


# Create a wrapper agent for PDF loading (to integrate with SequentialAgent)
pdf_loader_agent = LlmAgent(
    name="PDFLoaderAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are a PDF Loader Agent. Your role is to load PDF content from URLs when provided.

When the user provides a [REPORT_URL], use the load_pdf_from_url_tool to fetch the PDF content.
The tool will return the content formatted as [REPORT_CONTENT]...[/END_REPORT_CONTENT].

If no [REPORT_URL] is provided or it's "N/A", simply acknowledge that you'll use the provided [REPORT_CONTENT] directly.

After loading (or if no URL provided), return a message indicating the content is ready for processing.
Include the [REPORT_CONTENT] section in your response so downstream agents can access it.
""",
    tools=[load_pdf_from_url_tool],
    output_key="pdf_content",
)


# Note: We no longer export to Google Slides - main pipeline uses web slides generation instead
# The root_agent is kept for ADK-web compatibility but uses a simplified flow


# Create the main SequentialAgent pipeline
# Note: This root_agent is for ADK-web compatibility only
# The main pipeline execution uses PipelineOrchestrator which generates web slides (not Google Slides)
root_agent = SequentialAgent(
    name="PresentationGeneratorAgent",
    sub_agents=[
        pdf_loader_agent,                    # Step 0: Load PDF if URL provided
        report_understanding_agent,           # Step 1: Extract report knowledge
        outline_generator_agent,              # Step 2: Generate outline
        slide_and_script_generator_agent,     # Step 3: Generate slides and script
        # Note: Web slides generation is handled by PipelineOrchestrator, not in root_agent
    ],
    description="Generates presentations from research reports using a multi-agent pipeline (ADK-web compatibility only)",
)
