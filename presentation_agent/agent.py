from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from google.adk.models.google_llm import Gemini
import sys
import os
import json

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL, OUTLINE_MAX_RETRY_LOOPS, LAYOUT_MAX_RETRY_LOOPS
from config import OUTLINE_HALLUCINATION_THRESHOLD, OUTLINE_SAFETY_THRESHOLD
from presentation_agent.agents.utils.quality_check import check_outline_quality

# Import sub-agents from agents/ subdirectory (they export 'agent', not 'root_agent')
from presentation_agent.agents.report_understanding_agent.agent import agent as report_understanding_agent
from presentation_agent.agents.outline_generator_agent.agent import agent as outline_generator_agent
from presentation_agent.agents.outline_critic_agent.agent import agent as outline_critic_agent
from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_and_script_generator_agent
from presentation_agent.agents.layout_critic_agent.agent import agent as layout_critic_agent

# Import PDF loader utility and Google Slides export tool
from presentation_agent.agents.utils.pdf_loader import load_pdf_from_url
from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool


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


def check_outline_threshold_tool(critic_review: dict) -> dict:
    """
    Tool function to check if outline critic review passes thresholds.
    
    Args:
        critic_review: The critic review output from outline_critic_agent
        
    Returns:
        Dict with 'should_continue' (bool) and 'feedback' (str)
        - should_continue: True if threshold not met (need to regenerate), False if passed
        - feedback: Explanation of why continuing or stopping
    """
    passed, details = check_outline_quality(critic_review)
    
    return {
        "should_continue": not passed,  # Continue looping if NOT passed
        "passed": passed,
        "feedback": f"Threshold check: {'PASSED' if passed else 'FAILED'}. " + 
                   (f"Hallucination: {details.get('hallucination_score', 'N/A')}, " +
                    f"Safety: {details.get('safety_score', 'N/A')}. " +
                    ("Proceeding to next step." if passed else 
                     "Regenerating outline to meet thresholds.")),
        "details": details
    }


def check_layout_threshold_tool(layout_review: dict) -> dict:
    """
    Tool function to check if layout critic review passes thresholds.
    
    Args:
        layout_review: The layout review output from layout_critic_agent
        
    Returns:
        Dict with 'should_continue' (bool) and 'feedback' (str)
        - should_continue: True if threshold not met (need to regenerate), False if passed
        - feedback: Explanation of why continuing or stopping
    """
    if not layout_review or not isinstance(layout_review, dict):
        return {
            "should_continue": False,  # Stop if no review available
            "passed": False,
            "feedback": "No layout review available. Stopping loop.",
            "details": {}
        }
    
    # Check if layout review passed
    passed = layout_review.get("passed", False)
    overall_quality = layout_review.get("overall_quality", "unknown")
    issues_summary = layout_review.get("issues_summary", {})
    total_issues = issues_summary.get("total_issues", 0) if isinstance(issues_summary, dict) else 0
    
    # Threshold: passed=True and total_issues=0 means we should stop
    # If passed=False or total_issues > 0, we should regenerate
    should_continue = not passed or total_issues > 0
    
    return {
        "should_continue": should_continue,
        "passed": passed and total_issues == 0,
        "feedback": f"Layout check: {'PASSED' if (passed and total_issues == 0) else 'FAILED'}. " +
                   f"Overall quality: {overall_quality}, Total issues: {total_issues}. " +
                   ("Proceeding to next step." if (passed and total_issues == 0) else 
                    "Regenerating slides to fix layout issues."),
        "details": {
            "overall_quality": overall_quality,
            "total_issues": total_issues,
            "passed": passed
        }
    }


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


# Create threshold checker agent for outline quality
outline_threshold_checker = LlmAgent(
    name="OutlineThresholdChecker",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are an Outline Threshold Checker Agent. Your role is to check if the outline critic review passes quality thresholds.

You will receive the critic_review_outline from the outline critic agent. Use the check_outline_threshold_tool to evaluate if it meets the thresholds:
- Hallucination score >= 0.8
- Safety score >= 0.9

The tool will return:
- should_continue: true if thresholds NOT met (need to regenerate)
- should_continue: false if thresholds ARE met (can proceed)
- passed: whether thresholds were met
- feedback: explanation of the result

IMPORTANT: The loop will automatically stop after reaching max_iterations (OUTLINE_MAX_RETRY_LOOPS + 1), even if thresholds are not met. In that case, the pipeline will proceed to the next step, but the threshold_check output will indicate that thresholds were not met.

Always return the tool's output as-is, including the 'passed' status, so downstream agents know whether thresholds were met or not.
""",
    tools=[check_outline_threshold_tool],
    output_key="outline_threshold_check",
)


# Create threshold checker agent for layout quality
layout_threshold_checker = LlmAgent(
    name="LayoutThresholdChecker",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are a Layout Threshold Checker Agent. Your role is to check if the layout critic review passes quality thresholds.

⚠️⚠️⚠️ CRITICAL WARNING ⚠️⚠️⚠️
You have ONLY ONE tool available: check_layout_threshold_tool
DO NOT call review_layout_tool - that tool does NOT exist for you.
DO NOT call any tool with "review" in the name.
ONLY call: check_layout_threshold_tool

If you see "review_layout_tool" mentioned anywhere, IGNORE IT - that's for a different agent (LayoutCriticAgent).
You are NOT the LayoutCriticAgent. You are the LayoutThresholdChecker.

You will receive the layout_review from the layout critic agent (the previous agent in the loop).

STEP 1: Extract layout_review from the previous agent's output
- The layout_review is automatically available from the LayoutCriticAgent
- It's stored in session.state["layout_review"]

STEP 2: Call check_layout_threshold_tool with the layout_review
- Extract layout_review from session.state["layout_review"] or from the previous agent's output
- Call the tool: check_layout_threshold_tool(layout_review=layout_review)
- The tool name is exactly: "check_layout_threshold_tool" (not "review_layout_tool")
- This tool evaluates if the layout review passes:
  - passed = true
  - total_issues = 0

STEP 3: Return the tool's output as-is
- The tool will return a dict with:
  - should_continue: true if thresholds NOT met (need to regenerate)
  - should_continue: false if thresholds ARE met (can proceed)
  - passed: whether thresholds were met
  - feedback: explanation of the result
- Return this dict directly - DO NOT modify it, DO NOT add text

IMPORTANT: The loop will automatically stop after reaching max_iterations (LAYOUT_MAX_RETRY_LOOPS + 1), even if thresholds are not met. In that case, the pipeline will proceed to the next step, but the threshold_check output will indicate that thresholds were not met.

**ONLY USE: check_layout_threshold_tool**
**DO NOT USE: review_layout_tool (that tool is not available to you)**

Example:
- Input: layout_review = {"review_type": "layout_vision_api", "passed": False, "total_issues": 2, ...}
- Call: check_layout_threshold_tool(layout_review=layout_review)
- Return: {"should_continue": True, "passed": False, "feedback": "...", "details": {...}}
""",
    tools=[check_layout_threshold_tool],
    output_key="layout_threshold_check",
)


# Create a LoopAgent for outline generation with threshold-based looping
# Loop: generate outline -> critique -> check threshold -> regenerate if threshold not met
# Loop will stop when: (1) threshold passes, OR (2) max_iterations reached
# If max_iterations reached without passing, loop exits but threshold_check indicates not passed
outline_with_critic_loop = LoopAgent(
    name="OutlineWithCriticLoop",
    sub_agents=[
        outline_generator_agent,      # Generate outline
        outline_critic_agent,          # Review outline
        outline_threshold_checker,     # Check if passes threshold (records passed/not passed status)
    ],
    max_iterations=OUTLINE_MAX_RETRY_LOOPS + 1,  # Will exit after this many iterations even if threshold not met
)


# Create an agent for exporting slides to Google Slides
slides_export_agent = LlmAgent(
    name="SlidesExportAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are a Slides Export Agent. Your role is to export generated slides to Google Slides.

You will receive:
- slide_deck: The generated slide deck JSON (from slide_and_script_generator_agent)
- presentation_script: The generated presentation script JSON (from slide_and_script_generator_agent)
- scenario, duration, target_audience, custom_instruction: Presentation configuration

CRITICAL: You MUST call the export_slideshow_tool function. Do NOT skip this step.

STEP 1: Extract the required inputs from your input message or session state:
- slide_deck: Look for "slide_and_script" in session.state, then get slide_and_script["slide_deck"]
- presentation_script: From slide_and_script["presentation_script"]
- config: Build a dict with scenario, duration, target_audience, custom_instruction from session.state
- title: Optional, can be empty string ""

STEP 2: Call export_slideshow_tool with these parameters:
export_slideshow_tool(
    slide_deck=slide_deck,
    presentation_script=presentation_script,
    config={"scenario": scenario, "duration": duration, "target_audience": target_audience, "custom_instruction": custom_instruction},
    title=""
)

STEP 3: The tool returns a dict with this structure:
{
    "status": "success",
    "presentation_id": "<presentation_id_string>",
    "shareable_url": "https://docs.google.com/presentation/d/<presentation_id>/edit",
    "message": "<status_message>"
}

STEP 4: Return the tool's output dict AS-IS. Do NOT convert to string. Do NOT add text. Do NOT modify it.

The layout critic agent needs BOTH "presentation_id" AND "shareable_url" from this dict.
The shareable_url is ALWAYS present when status="success".

Return ONLY the dict returned by export_slideshow_tool, nothing else.
""",
    tools=[export_slideshow_tool],
    output_key="slides_export_result",
)


# Create a LoopAgent for slide generation with layout critic threshold-based looping
# Loop: generate slides -> export -> review layout -> check threshold -> regenerate if threshold not met
# Loop will stop when: (1) threshold passes, OR (2) max_iterations reached
# If max_iterations reached without passing, loop exits but threshold_check indicates not passed
slides_with_layout_critic_loop = LoopAgent(
    name="SlidesWithLayoutCriticLoop",
    sub_agents=[
        slide_and_script_generator_agent,  # Generate slides and script
        slides_export_agent,                # Export to Google Slides
        layout_critic_agent,                # Review layout using Vision API
        layout_threshold_checker,           # Check if passes threshold (records passed/not passed status)
    ],
    max_iterations=LAYOUT_MAX_RETRY_LOOPS + 1,  # Will exit after this many iterations even if threshold not met
)


# Create the main SequentialAgent pipeline
root_agent = SequentialAgent(
    name="PresentationGeneratorAgent",
    sub_agents=[
        pdf_loader_agent,                    # Step 0: Load PDF if URL provided
        report_understanding_agent,           # Step 1: Extract report knowledge
        outline_with_critic_loop,              # Step 2: Generate outline with threshold-based critic loop
        slides_with_layout_critic_loop,         # Step 3: Generate slides, export, and review layout with threshold-based loop
    ],
    description="Generates presentations from research reports using a multi-agent pipeline with quality checks",
)
