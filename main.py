"""
Main script for local development and testing of the presentation generation pipeline.
"""

import os
import asyncio
import json
import datetime
import re
import logging
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
import webbrowser

from config import PresentationConfig, LAYOUT_MAX_RETRY_LOOPS
# Import individual agents for manual orchestration
from presentation_agent.agents.report_understanding_agent.agent import agent as report_understanding_agent
from presentation_agent.agents.outline_generator_agent.agent import agent as outline_generator_agent
from presentation_agent.agents.outline_critic_agent.agent import agent as outline_critic_agent
from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_and_script_generator_agent
from presentation_agent.agents.chart_generator_agent.agent import agent as chart_generator_agent
from presentation_agent.agents.layout_critic_agent.agent import agent as layout_critic_agent

# Import tools and utilities
from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool
from presentation_agent.agents.utils.pdf_loader import load_pdf
from presentation_agent.agents.utils.helpers import extract_output_from_events, save_json_output, preview_json
from presentation_agent.agents.utils.observability import (
    get_observability_logger,
    AgentStatus
)
from presentation_agent.agents.utils.quality_check import check_outline_quality


def parse_duration_to_seconds(duration_input) -> int:
    """
    Parse duration to seconds.
    Accepts either a string (e.g., "20 minutes") or an integer (assumed to be seconds).
    Examples: "20 minutes" -> 1200, "10 minutes" -> 600, "1 hour" -> 3600, 1200 -> 1200
    """
    # If it's already an integer, assume it's already in seconds
    if isinstance(duration_input, int):
        return duration_input
    
    # If it's a float, convert to int (assume seconds)
    if isinstance(duration_input, float):
        return int(duration_input)
    
    # If it's not a string, try to convert
    if not isinstance(duration_input, str):
        try:
            return int(duration_input)
        except:
            return 1200  # Default 20 minutes
    
    duration_str = duration_input.lower().strip()
    
    # Extract number and unit
    match = re.match(r'(\d+)\s*(minute|minutes|min|hour|hours|hr|second|seconds|sec)', duration_str)
    if not match:
        # Default to minutes if format is unclear
        try:
            num = int(re.search(r'\d+', duration_str).group())
            return num * 60  # Assume minutes
        except:
            return 1200  # Default 20 minutes
    
    num = int(match.group(1))
    unit = match.group(2).lower()
    
    if unit in ['minute', 'minutes', 'min']:
        return num * 60
    elif unit in ['hour', 'hours', 'hr']:
        return num * 3600
    elif unit in ['second', 'seconds', 'sec']:
        return num
    else:
        return num * 60  # Default to minutes


async def run_presentation_pipeline(
    config: PresentationConfig,
    output_dir: str = "presentation_agent/output",
    include_critics: bool = True,
    save_intermediate: bool = True,
    open_browser: bool = True,
):
    """
    Run the complete presentation generation pipeline using MANUAL orchestration.
    
    This approach:
    - Uses ADK agents (still compatible with ADK-web UI for individual agent testing)
    - Orchestrates them manually (more reliable, easier to debug)
    - Uses custom observability module (full observability retained)
    - Directly calls export tool (bypasses callback issues)
    
    Args:
        config: PresentationConfig object with all configuration
        output_dir: Directory to save outputs
        include_critics: Whether to include critic agents
        save_intermediate: Whether to save intermediate outputs
        open_browser: Whether to open Google Slides URL in browser after generation
        
    Returns:
        Dictionary with all generated outputs
    """
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Initialize observability
    trace_file = f"{output_dir}/trace_history.json"
    obs_logger = get_observability_logger(
        log_file=f"{output_dir}/observability.log",
        trace_file=trace_file
    )
    obs_logger.start_pipeline("presentation_pipeline")
    
    # Load PDF if URL provided
    if config.report_url and not config.report_content:
        print(f"📄 Loading PDF from URL: {config.report_url}")
        config.report_content = load_pdf(report_url=config.report_url)
        # Count lines and words for better logging
        lines = config.report_content.split('\n')
        words = config.report_content.split()
        print(f"✅ Loaded PDF: {len(config.report_content)} characters, {len(lines)} lines, {len(words)} words")
        # Don't print the full content to avoid cluttering logs
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="presentation_agent",
        user_id="user"
    )
    
    # Set up session state
    session.state.update(config.to_dict())
    
    # Log which fields are provided vs need inference
    print("\n📋 Input Configuration:")
    print("=" * 60)
    scenario_provided = config.scenario and config.scenario.strip()
    target_audience_provided = config.target_audience and config.target_audience.strip()
    custom_instruction_provided = config.custom_instruction and config.custom_instruction.strip()
    
    print(f"  ✅ scenario: {'PROVIDED' if scenario_provided else 'NOT PROVIDED (will be inferred)'}")
    if scenario_provided:
        print(f"     Value: {config.scenario}")
    
    print(f"  ✅ target_audience: {'PROVIDED' if target_audience_provided else 'NOT PROVIDED (will be inferred)'}")
    if target_audience_provided:
        print(f"     Value: {config.target_audience}")
    
    print(f"  ✅ custom_instruction: {'PROVIDED' if custom_instruction_provided else 'NOT PROVIDED (will be omitted)'}")
    if custom_instruction_provided:
        print(f"     Value: {config.custom_instruction}")
    
    print(f"  ✅ duration: PROVIDED")
    print(f"     Value: {config.duration}")
    print(f"  ✅ report_url: {'PROVIDED' if config.report_url else 'NOT PROVIDED'}")
    if config.report_url:
        print(f"     Value: {config.report_url}")
    print("=" * 60)
    
    # Build initial message (same format as server.py)
    # Handle optional fields
    scenario_section = (
        f"[SCENARIO]\n{config.scenario}\n\n"
        if scenario_provided
        else "[SCENARIO]\nN/A\n\n"
    )
    
    target_audience_section = (
        f"[TARGET_AUDIENCE]\n{config.target_audience}\n\n"
        if target_audience_provided
        else "[TARGET_AUDIENCE]\nN/A\n\n"
    )
    
    custom_instruction_section = (
        f"[CUSTOM_INSTRUCTION]\n{config.custom_instruction}\n\n"
        if custom_instruction_provided
        else ""
    )
    
    initial_message = f"""
{scenario_section}[DURATION]
{config.duration}

{target_audience_section}{custom_instruction_section}[REPORT_URL]
{config.report_url or 'N/A'}

[REPORT_CONTENT]
{config.report_content or ''}
[END_REPORT_CONTENT]

Your task:
- Use ONLY the above information.
- Generate a complete presentation following the pipeline.
- Do NOT ask any questions.
- Do NOT invent information not in the report_content.
"""
    
    # Run pipeline using MANUAL orchestration
    print("\n🚀 Starting pipeline execution with MANUAL orchestration...")
    print("=" * 60)
    
    outputs = {}
    
    try:
        # Step 1: Report Understanding Agent
        print("\n📊 Step 1: Report Understanding Agent")
        obs_logger.start_agent_execution("ReportUnderstandingAgent", output_key="report_knowledge")
        runner = InMemoryRunner(agent=report_understanding_agent)
        events = await runner.run_debug(initial_message, session_id=session.id)
        report_knowledge = extract_output_from_events(events, "report_knowledge")
        
        if report_knowledge:
            # Parse report_knowledge if it's a string
            if isinstance(report_knowledge, str):
                try:
                    report_knowledge = json.loads(report_knowledge.strip())
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    cleaned = report_knowledge.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:].lstrip()
                    elif cleaned.startswith("```"):
                        cleaned = cleaned[3:].lstrip()
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3].rstrip()
                    try:
                        report_knowledge = json.loads(cleaned)
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Warning: Could not parse report_knowledge as JSON: {e}")
            
            # Log inferred values
            print("\n🔍 Inference Results:")
            print("=" * 60)
            inferred_scenario = report_knowledge.get("scenario", "N/A")
            inferred_audience = report_knowledge.get("audience_profile", {}).get("primary_audience", "N/A")
            
            if not scenario_provided:
                print(f"  🧠 scenario: INFERRED")
                print(f"     Inferred Value: {inferred_scenario}")
            else:
                print(f"  ✅ scenario: PROVIDED (not inferred)")
                print(f"     Provided Value: {config.scenario}")
                if inferred_scenario != config.scenario:
                    print(f"     ⚠️  Note: Agent output differs from input: {inferred_scenario}")
            
            if not target_audience_provided:
                print(f"  🧠 target_audience: INFERRED")
                print(f"     Inferred Value: {inferred_audience}")
                audience_level = report_knowledge.get("audience_profile", {}).get("assumed_knowledge_level", "N/A")
                print(f"     Knowledge Level: {audience_level}")
            else:
                print(f"  ✅ target_audience: PROVIDED (not inferred)")
                print(f"     Provided Value: {config.target_audience}")
            
            print("=" * 60)
            
            outputs["report_knowledge"] = report_knowledge
            session.state["report_knowledge"] = report_knowledge
            obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
            if save_intermediate:
                output_file = f"{output_dir}/report_knowledge.json"
                save_json_output(report_knowledge, output_file)
                print(f"✅ Report knowledge saved to: {output_file}")
        else:
            obs_logger.finish_agent_execution(AgentStatus.FAILED, "No output generated", has_output=False)
            raise ValueError("ReportUnderstandingAgent failed to generate output")
        
        # Step 2: Outline Generation with Critic Loop
        print("\n📝 Step 2: Outline Generation with Critic Loop")
        outline_retries = 0
        max_outline_retries = 3
        
        while outline_retries < max_outline_retries:
            # Outline Generator
            obs_logger.start_agent_execution("OutlineGeneratorAgent", output_key="presentation_outline", retry_count=outline_retries)
            runner = InMemoryRunner(agent=outline_generator_agent)
            events = await runner.run_debug(
                f"Based on the report knowledge:\n{json.dumps(report_knowledge, indent=2)}\n\nGenerate a presentation outline.",
                session_id=session.id
            )
            presentation_outline = extract_output_from_events(events, "presentation_outline")
            
            if not presentation_outline:
                obs_logger.finish_agent_execution(AgentStatus.FAILED, "No outline generated", has_output=False)
                outline_retries += 1
                continue
            
            session.state["presentation_outline"] = presentation_outline
            
            # Outline Critic (if enabled)
            if include_critics:
                obs_logger.start_agent_execution("OutlineCriticAgent", output_key="critic_review_outline")
                runner = InMemoryRunner(agent=outline_critic_agent)
                # Build proper input message with all required context
                # Build critic input with optional fields handling
                scenario_section = (
                    f"[SCENARIO]\n{config.scenario}\n\n"
                    if config.scenario and config.scenario.strip()
                    else "[SCENARIO]\nN/A\n\n"
                )
                target_audience_section = (
                    f"[TARGET_AUDIENCE]\n{config.target_audience}\n\n"
                    if config.target_audience
                    else "[TARGET_AUDIENCE]\nN/A\n\n"
                )
                custom_instruction_section = (
                    f"[CUSTOM_INSTRUCTION]\n{config.custom_instruction}\n\n"
                    if config.custom_instruction and config.custom_instruction.strip()
                    else ""
                )
                
                critic_input = f"""[PRESENTATION_OUTLINE]
{json.dumps(presentation_outline, indent=2)}
[END_PRESENTATION_OUTLINE]

[REPORT_KNOWLEDGE]
{json.dumps(report_knowledge, indent=2)}
[END_REPORT_KNOWLEDGE]

{scenario_section}[DURATION]
{config.duration}

{target_audience_section}{custom_instruction_section}Review this outline for quality, hallucination, and safety."""
                events = await runner.run_debug(critic_input, session_id=session.id)
                critic_review = extract_output_from_events(events, "critic_review_outline")
                
                if critic_review:
                    passed, quality_details = check_outline_quality(critic_review)
                    obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
                    
                    if passed:
                        feedback = quality_details.get('failure_reasons', [])
                        if feedback:
                            print(f"✅ Outline quality check passed")
                        else:
                            print(f"✅ Outline quality check passed (scores: hallucination={quality_details.get('hallucination_score', 'N/A')}, safety={quality_details.get('safety_score', 'N/A')})")
                        break
                    else:
                        failure_reasons = quality_details.get('failure_reasons', ['Quality check failed'])
                        feedback = '; '.join(failure_reasons)
                        print(f"⚠️  Outline quality check failed: {feedback}")
                        outline_retries += 1
                        obs_logger.log_retry("OutlineGeneratorAgent", outline_retries, feedback)
                        continue
                else:
                    obs_logger.finish_agent_execution(AgentStatus.FAILED, "No critic review generated", has_output=False)
                    # Continue anyway if critic fails
                    break
            else:
                break
        
        if not presentation_outline:
            raise ValueError("OutlineGeneratorAgent failed to generate outline after retries")
        
        outputs["presentation_outline"] = presentation_outline
        if save_intermediate:
            output_file = f"{output_dir}/presentation_outline.json"
            save_json_output(presentation_outline, output_file)
            print(f"✅ Presentation outline saved to: {output_file}")
        
        # Step 3: Slide and Script Generation
        print("\n🎨 Step 3: Slide and Script Generation")
        obs_logger.start_agent_execution("SlideAndScriptGeneratorAgent", output_key="slide_and_script")
        runner = InMemoryRunner(agent=slide_and_script_generator_agent)
        events = await runner.run_debug(
            f"Generate slides and script based on:\nOutline: {json.dumps(presentation_outline, indent=2)}\nReport Knowledge: {json.dumps(report_knowledge, indent=2)}",
            session_id=session.id
        )
        slide_and_script = extract_output_from_events(events, "slide_and_script")
        
        if not slide_and_script:
            obs_logger.finish_agent_execution(AgentStatus.FAILED, "No slide_and_script generated", has_output=False)
            raise ValueError("SlideAndScriptGeneratorAgent failed to generate output")
        
        # Parse slide_and_script
        if isinstance(slide_and_script, str):
            try:
                cleaned = slide_and_script.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:].lstrip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:].lstrip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].rstrip()
                slide_and_script = json.loads(cleaned)
            except json.JSONDecodeError as e:
                print(f"⚠️  Warning: Could not parse slide_and_script as JSON: {e}")
                print(f"   Error at line {e.lineno}, column {e.colno}")
                # Show context around the error
                lines = cleaned.split('\n')
                error_line_idx = e.lineno - 1
                start_idx = max(0, error_line_idx - 2)
                end_idx = min(len(lines), error_line_idx + 3)
                print(f"   Context around error (lines {start_idx+1}-{end_idx}):")
                for i in range(start_idx, end_idx):
                    marker = ">>> " if i == error_line_idx else "    "
                    print(f"   {marker}{i+1}: {lines[i]}")
                # Try to fix common JSON issues
                print(f"   Attempting to fix common JSON issues...")
                try:
                    fixed = cleaned
                    
                    # Fix 1: Remove trailing commas before closing brackets/braces
                    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
                    
                    # Fix 2: Remove comments (// or /* */) - sometimes agents add these
                    fixed = re.sub(r'//.*?$', '', fixed, flags=re.MULTILINE)
                    fixed = re.sub(r'/\*.*?\*/', '', fixed, flags=re.DOTALL)
                    
                    slide_and_script = json.loads(fixed)
                    print(f"   ✅ Fixed JSON parsing issue (removed trailing commas/comments)")
                except json.JSONDecodeError as e2:
                    print(f"   ❌ Could not auto-fix JSON. Error after fix attempt: {e2}")
                    print(f"   Original error: {e}")
                    # Save the problematic JSON for debugging
                    debug_file = f"{output_dir}/slide_and_script_raw_debug.json"
                    try:
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            f.write(cleaned)
                        print(f"   📄 Raw output saved to: {debug_file}")
                    except Exception as save_error:
                        print(f"   ⚠️  Could not save debug file: {save_error}")
                    obs_logger.finish_agent_execution(AgentStatus.FAILED, f"JSON parse error: {e}", has_output=False)
                    raise
        
        slide_deck = slide_and_script.get("slide_deck")
        presentation_script = slide_and_script.get("presentation_script")
        
        if slide_deck:
            outputs["slide_deck"] = slide_deck
            session.state["slide_deck"] = slide_deck
            if save_intermediate:
                slide_deck_file = f"{output_dir}/slide_deck.json"
                save_json_output(slide_deck, slide_deck_file)
                print(f"✅ Slide deck saved to: {slide_deck_file}")
        
        if presentation_script:
            outputs["presentation_script"] = presentation_script
            session.state["presentation_script"] = presentation_script
            if save_intermediate:
                script_file = f"{output_dir}/presentation_script.json"
                save_json_output(presentation_script, script_file)
                print(f"✅ Presentation script saved to: {script_file}")
        
        obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        
        # Step 3.5: Chart Generation (if needed)
        print("\n📊 Step 3.5: Chart Generation")
        obs_logger.start_agent_execution("ChartGeneratorAgent", output_key="chart_generation_status")
        
        # Check if any slides need charts
        slides_with_charts = []
        if slide_deck and isinstance(slide_deck, dict):
            for slide in slide_deck.get('slides', []):
                visual_elements = slide.get('visual_elements', {})
                if visual_elements.get('charts_needed', False) and visual_elements.get('chart_spec'):
                    slides_with_charts.append(slide.get('slide_number'))
        
        if slides_with_charts:
            print(f"   📊 Found {len(slides_with_charts)} slide(s) needing charts: {slides_with_charts}")
            
            # Run ChartGeneratorAgent
            # The agent will validate chart_spec, and the callback will generate charts
            chart_input = json.dumps({"slide_deck": slide_deck}, separators=(',', ':'))
            runner = InMemoryRunner(agent=chart_generator_agent)
            chart_events = await runner.run_debug(
                chart_input,
                session_id=session.id
            )
            
            # Extract chart generation status
            chart_status = extract_output_from_events(chart_events, "chart_generation_status")
            
            # The callback has already updated slide_deck in session.state
            # Get the updated slide_deck
            updated_slide_deck = session.state.get("slide_deck") or slide_deck
            
            # Verify charts were generated
            charts_generated_count = 0
            for slide in updated_slide_deck.get('slides', []):
                visual_elements = slide.get('visual_elements', {})
                chart_data = visual_elements.get('chart_data')
                if chart_data and chart_data != "PLACEHOLDER_CHART_DATA" and len(chart_data) > 100:
                    charts_generated_count += 1
            
            if charts_generated_count > 0:
                print(f"   ✅ Successfully generated {charts_generated_count} chart(s)")
                slide_deck = updated_slide_deck  # Use updated slide_deck with chart_data
                outputs["slide_deck"] = slide_deck
                session.state["slide_deck"] = slide_deck
            else:
                print(f"   ⚠️  Warning: No charts were generated (check logs for errors)")
            
            obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        else:
            print("   ℹ️  No charts needed for this presentation")
            obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=False)
        
        # Step 4: Google Slides Export (DIRECT CALL - bypasses callback issues)
        print("\n📤 Step 4: Google Slides Export")
        obs_logger.start_agent_execution("SlidesExportAgent", output_key="slides_export_result")
        
        if not slide_deck or not presentation_script:
            obs_logger.finish_agent_execution(AgentStatus.FAILED, "Missing slide_deck or presentation_script", has_output=False)
            raise ValueError("Cannot export: missing slide_deck or presentation_script")
        
        # Direct tool call (reliable, bypasses callback issues)
        config_dict = {
            'scenario': config.scenario,
            'duration': config.duration,
            'target_audience': config.target_audience,
            'custom_instruction': config.custom_instruction
        }
        
        print("   🚀 Calling export_slideshow_tool directly...")
        export_result = export_slideshow_tool(
            slide_deck=slide_deck,
            presentation_script=presentation_script,
            config=config_dict,
            title=""
        )
        
        if export_result.get('status') in ['success', 'partial_success']:
            outputs["slideshow_export_result"] = export_result
            session.state["slideshow_export_result"] = export_result
            
            presentation_id = export_result.get("presentation_id")
            shareable_url = export_result.get("shareable_url") or f"https://docs.google.com/presentation/d/{presentation_id}/edit"
            
            if presentation_id:
                id_file = f"{output_dir}/presentation_slides_id.txt"
                url_file = f"{output_dir}/presentation_slides_url.txt"
                
                with open(id_file, 'w') as f:
                    f.write(presentation_id)
                with open(url_file, 'w') as f:
                    f.write(shareable_url)
                
                print(f"\n✅ Google Slides export successful!")
                print(f"   Presentation ID: {presentation_id}")
                print(f"   🔗 Shareable URL: {shareable_url}")
                print(f"\n📄 Presentation ID saved to: {id_file}")
                print(f"📄 Shareable URL saved to: {url_file}")
                
                # Open in browser if requested
                if open_browser:
                    print(f"\n🌐 Opening Google Slides in browser...")
                    try:
                        webbrowser.open(shareable_url)
                        print(f"   ✅ Opened: {shareable_url}")
                    except Exception as e:
                        print(f"   ⚠️  Could not open browser: {e}")
                        print(f"   Please manually open: {shareable_url}")
            
            if save_intermediate:
                export_file = f"{output_dir}/slideshow_export_result.json"
                save_json_output(export_result, export_file)
                print(f"📄 Export result saved to: {export_file}")
            
            obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        else:
            error_msg = export_result.get('error', 'Unknown error')
            obs_logger.finish_agent_execution(AgentStatus.FAILED, error_msg, has_output=False)
            print(f"⚠️  Google Slides export failed: {error_msg}")
        
        # Step 5: Layout Critic with Retry Loop (optional, if export succeeded)
        if include_critics and export_result.get('status') in ['success', 'partial_success']:
            print("\n🎨 Step 5: Layout Review with Retry Loop")
            layout_retries = 0
            max_layout_retries = LAYOUT_MAX_RETRY_LOOPS + 1  # +1 because first attempt is not a retry
            
            while layout_retries < max_layout_retries:
                if layout_retries > 0:
                    print(f"\n🔄 Layout Review Retry {layout_retries}/{LAYOUT_MAX_RETRY_LOOPS}")
                
                # Layout Critic
                obs_logger.start_agent_execution("LayoutCriticAgent", output_key="layout_review", retry_count=layout_retries)
                
                shareable_url = export_result.get("shareable_url") or f"https://docs.google.com/presentation/d/{export_result.get('presentation_id')}/edit"
                if shareable_url:
                    # Store slides_export_result in session.state so agent can access it
                    session.state["slides_export_result"] = export_result
                    
                    # Build input message with slides_export_result in the format agent expects
                    layout_input = f"""The SlidesExportAgent has completed. Here is the slides_export_result:

{json.dumps(export_result, separators=(',', ':'))}

Extract the shareable_url from slides_export_result and call review_layout_tool with it to review the layout."""
                    
                    runner = InMemoryRunner(agent=layout_critic_agent)
                    events = await runner.run_debug(layout_input, session_id=session.id)
                    
                    # Extract layout_review - try multiple methods
                    layout_review = extract_output_from_events(events, "layout_review")
                    
                    # Also check session.state (callback might have stored it there)
                    if not layout_review and session.state.get("layout_review"):
                        layout_review = session.state.get("layout_review")
                        print(f"✅ [DEBUG] Found layout_review in session.state (from callback)")
                    
                    # Debug: Log what we got from extract_output_from_events
                    if layout_review:
                        print(f"🔍 [DEBUG] extract_output_from_events returned type: {type(layout_review).__name__}")
                        if isinstance(layout_review, str):
                            print(f"   [DEBUG] String length: {len(layout_review)}, first 100 chars: {repr(layout_review[:100])}")
                        elif isinstance(layout_review, dict):
                            print(f"   [DEBUG] Dict keys: {list(layout_review.keys())[:5]}")
                    else:
                        print("🔍 [DEBUG] extract_output_from_events returned None")
                    
                    # If not found, try to extract from agent's text content (fallback)
                    if not layout_review:
                        print("🔍 [DEBUG] Checking agent text content for JSON...")
                        for event in reversed(events):
                            if hasattr(event, 'content') and event.content:
                                if hasattr(event.content, 'parts') and event.content.parts:
                                    for part in event.content.parts:
                                        if hasattr(part, 'text') and part.text:
                                            text = part.text.strip()
                                            # Look for JSON object in the text
                                            start_idx = text.find("{")
                                            if start_idx != -1:
                                                # Try to parse from the first { onwards
                                                try:
                                                    # Find matching closing brace
                                                    brace_count = 0
                                                    end_idx = start_idx
                                                    for i in range(start_idx, len(text)):
                                                        if text[i] == '{':
                                                            brace_count += 1
                                                        elif text[i] == '}':
                                                            brace_count -= 1
                                                            if brace_count == 0:
                                                                end_idx = i
                                                                break
                                                    if end_idx > start_idx:
                                                        json_str = text[start_idx:end_idx+1]
                                                        # Convert Python-style JSON to JSON-compliant
                                                        json_str = re.sub(r'\bTrue\b', 'true', json_str)
                                                        json_str = re.sub(r'\bFalse\b', 'false', json_str)
                                                        json_str = re.sub(r'\bNone\b', 'null', json_str)
                                                        # Fix invalid escape sequences
                                                        json_str = re.sub(r"\\'", "'", json_str)
                                                        parsed = json.loads(json_str)
                                                        # Extract review_layout_tool_response if it exists
                                                        if isinstance(parsed, dict) and "review_layout_tool_response" in parsed:
                                                            layout_review = parsed["review_layout_tool_response"]
                                                            print(f"✅ [DEBUG] Extracted layout_review from agent text content (extracted from review_layout_tool_response)")
                                                            break
                                                        elif isinstance(parsed, dict) and ('review_type' in parsed or 'passed' in parsed):
                                                            layout_review = parsed
                                                            print(f"✅ [DEBUG] Extracted layout_review from agent text content")
                                                            break
                                                except (json.JSONDecodeError, ValueError):
                                                    pass
                                    if layout_review:
                                        break
                            if layout_review:
                                break
                    
                    # If not found, try to extract directly from tool_results
                    if not layout_review:
                        print("🔍 [DEBUG] layout_review not found in state_delta, checking tool_results directly...")
                        import logging
                        logger = logging.getLogger(__name__)
                        for i, event in enumerate(reversed(events)):
                            agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
                            if hasattr(event, 'actions') and event.actions:
                                if hasattr(event.actions, 'tool_results') and event.actions.tool_results:
                                    logger.info(f"   Found {len(event.actions.tool_results)} tool_results in event {len(events)-1-i} ({agent_name})")
                                    for tr_idx, tool_result in enumerate(event.actions.tool_results):
                                        if hasattr(tool_result, 'response'):
                                            response = tool_result.response
                                            # Check if response is the layout review dict
                                            if isinstance(response, dict):
                                                # Check if it's wrapped in review_layout_tool_response
                                                if "review_layout_tool_response" in response:
                                                    layout_review = response["review_layout_tool_response"]
                                                    print(f"✅ [DEBUG] Found layout_review in tool_result {tr_idx} (extracted from review_layout_tool_response)")
                                                    break
                                                elif ('review_type' in response and 'layout' in str(response.get('review_type', ''))) or \
                                                   ('total_slides_reviewed' in response) or \
                                                   ('passed' in response and 'overall_quality' in response) or \
                                                   ('presentation_id' in response and 'issues_summary' in response):
                                                    layout_review = response
                                                    print(f"✅ [DEBUG] Found layout_review in tool_result {tr_idx} of event {len(events)-1-i}")
                                                    break
                                            elif isinstance(response, str):
                                                # Try to parse as JSON
                                                try:
                                                    # Convert Python-style JSON to JSON-compliant
                                                    json_str = re.sub(r'\bTrue\b', 'true', response)
                                                    json_str = re.sub(r'\bFalse\b', 'false', json_str)
                                                    json_str = re.sub(r'\bNone\b', 'null', json_str)
                                                    # Fix invalid escape sequences
                                                    json_str = re.sub(r"\\'", "'", json_str)
                                                    parsed = json.loads(json_str)
                                                    # Extract review_layout_tool_response if it exists
                                                    if isinstance(parsed, dict) and "review_layout_tool_response" in parsed:
                                                        layout_review = parsed["review_layout_tool_response"]
                                                        print(f"✅ [DEBUG] Parsed layout_review from tool_result {tr_idx} string (extracted from review_layout_tool_response)")
                                                        break
                                                    elif isinstance(parsed, dict) and ('review_type' in parsed or 'passed' in parsed):
                                                        layout_review = parsed
                                                        print(f"✅ [DEBUG] Parsed layout_review from tool_result {tr_idx} string")
                                                        break
                                                except json.JSONDecodeError:
                                                    pass
                                        if layout_review:
                                            break
                                if layout_review:
                                    break
                    
                    # Parse layout_review if it's a string
                    if isinstance(layout_review, str):
                        try:
                            cleaned = layout_review.strip()
                            # Remove markdown code blocks if present
                            if cleaned.startswith("```json"):
                                cleaned = cleaned[7:].lstrip()
                            elif cleaned.startswith("```"):
                                cleaned = cleaned[3:].lstrip()
                            if cleaned.endswith("```"):
                                cleaned = cleaned[:-3].rstrip()
                            
                            # Convert Python-style JSON (True/False/None) to JSON-compliant (true/false/null)
                            # Use regex to replace Python booleans and None with JSON equivalents
                            # Replace True with true (but not in strings)
                            cleaned = re.sub(r'\bTrue\b', 'true', cleaned)
                            # Replace False with false (but not in strings)
                            cleaned = re.sub(r'\bFalse\b', 'false', cleaned)
                            # Replace None with null (but not in strings)
                            cleaned = re.sub(r'\bNone\b', 'null', cleaned)
                            
                            # Fix invalid escape sequences (e.g., \' should be just ')
                            # In JSON, single quotes don't need escaping, so \' is invalid
                            cleaned = re.sub(r"\\'", "'", cleaned)
                            
                            # Try to parse directly first
                            try:
                                parsed = json.loads(cleaned)
                                # Extract review_layout_tool_response if it exists
                                if isinstance(parsed, dict) and "review_layout_tool_response" in parsed:
                                    layout_review = parsed["review_layout_tool_response"]
                                    print("✅ [DEBUG] Parsed layout_review from string and extracted review_layout_tool_response")
                                else:
                                    layout_review = parsed
                                    print("✅ [DEBUG] Parsed layout_review from string")
                            except json.JSONDecodeError:
                                # If direct parse fails, try to find JSON object in the string
                                # Look for first { and matching last }
                                start_idx = cleaned.find("{")
                                if start_idx != -1:
                                    # Find the matching closing brace
                                    brace_count = 0
                                    end_idx = start_idx
                                    for i in range(start_idx, len(cleaned)):
                                        if cleaned[i] == '{':
                                            brace_count += 1
                                        elif cleaned[i] == '}':
                                            brace_count -= 1
                                            if brace_count == 0:
                                                end_idx = i
                                                break
            
                                    if end_idx > start_idx:
                                        json_str = cleaned[start_idx:end_idx+1]
                                        # Convert Python booleans in extracted JSON too
                                        json_str = re.sub(r'\bTrue\b', 'true', json_str)
                                        json_str = re.sub(r'\bFalse\b', 'false', json_str)
                                        json_str = re.sub(r'\bNone\b', 'null', json_str)
                                        # Fix invalid escape sequences
                                        json_str = re.sub(r"\\'", "'", json_str)
                                        parsed = json.loads(json_str)
                                        # Extract review_layout_tool_response if it exists
                                        if isinstance(parsed, dict) and "review_layout_tool_response" in parsed:
                                            layout_review = parsed["review_layout_tool_response"]
                                            print(f"✅ [DEBUG] Extracted and parsed JSON from string, extracted review_layout_tool_response (start={start_idx}, end={end_idx})")
                                        else:
                                            layout_review = parsed
                                            print(f"✅ [DEBUG] Extracted and parsed JSON from string (start={start_idx}, end={end_idx})")
                                    else:
                                        raise json.JSONDecodeError("No matching closing brace found", cleaned, start_idx)
                                else:
                                    raise json.JSONDecodeError("No JSON object found in string", cleaned, 0)
                        except json.JSONDecodeError as e:
                            print(f"⚠️  Warning: Could not parse layout_review as JSON: {e}")
                            print(f"   [DEBUG] First 100 chars of layout_review: {repr(layout_review[:100] if layout_review else 'None')}")
                            layout_review = None
                    
                    if layout_review and isinstance(layout_review, dict):
                        # Save layout_review to session.state for retry compression
                        session.state["layout_review"] = layout_review
                        
                        # Check if layout review passed
                        passed = layout_review.get("passed", False)
                        issues_summary = layout_review.get("issues_summary", {})
                        total_issues = issues_summary.get("total_issues", 0) if isinstance(issues_summary, dict) else 0
                        overall_quality = layout_review.get("overall_quality", "unknown")
                        
                        # Check for text overlap specifically
                        has_overlap = False
                        if issues_summary and isinstance(issues_summary, dict):
                            overlaps_detected = issues_summary.get("overlaps_detected", 0)
                            has_overlap = overlaps_detected > 0
                        
                        obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
                        
                        if save_intermediate:
                            review_file = f"{output_dir}/layout_review.json"
                            save_json_output(layout_review, review_file)
                            print(f"✅ Layout review saved to: {review_file}")
                        
                        # Check if layout passes (no issues)
                        if passed and total_issues == 0:
                            print(f"✅ Layout review passed! Quality: {overall_quality}, Issues: {total_issues}")
                            outputs["layout_review"] = layout_review
                            break
                        else:
                            print(f"⚠️  Layout review failed: Quality: {overall_quality}, Issues: {total_issues}, Overlaps: {has_overlap}")
                            
                            # If we've reached max retries, save the review and exit
                            if layout_retries >= LAYOUT_MAX_RETRY_LOOPS:
                                print(f"⚠️  Reached maximum layout retry attempts ({LAYOUT_MAX_RETRY_LOOPS}). Proceeding with current slides.")
                                outputs["layout_review"] = layout_review
                                break
                            
                            # Prepare feedback for slide regeneration
                            feedback_details = []
                            if layout_review.get("issues"):
                                for slide_issue in layout_review.get("issues", []):
                                    slide_num = slide_issue.get("slide_number")
                                    for issue in slide_issue.get("issues", []):
                                        issue_type = issue.get("type")
                                        severity = issue.get("severity", "minor")
                                        
                                        if issue_type == "text_overlap":
                                            for detail in issue.get("details", []):
                                                word1 = detail.get("word1", "text")
                                                word2 = detail.get("word2", "text")
                                                feedback_details.append(f"Slide {slide_num}: Words '{word1}' and '{word2}' overlap ({severity} severity).")
                                        elif issue_type == "text_overflow":
                                            for detail in issue.get("details", []):
                                                text = detail.get("text", "text")
                                                feedback_details.append(f"Slide {slide_num}: Text '{text}' overflows slide boundaries.")
                                        elif issue_type == "spacing":
                                            for detail in issue.get("details", []):
                                                feedback_details.append(f"Slide {slide_num}: Spacing issue: {detail.get('description', 'Inadequate whitespace')}.")
                                        elif issue_type == "alignment":
                                            for detail in issue.get("details", []):
                                                feedback_details.append(f"Slide {slide_num}: Alignment issue: {detail.get('description', 'Elements not properly aligned')}.")
                            
                            detailed_feedback = "\n- " + "\n- ".join(feedback_details) if feedback_details else "General layout issues detected."
                            
                            # Regenerate slides with feedback
                            layout_retries += 1
                            obs_logger.log_retry("SlideAndScriptGeneratorAgent", layout_retries, f"Layout issues: {detailed_feedback}")
                            
                            print(f"\n🔄 Regenerating slides to fix layout issues (Attempt {layout_retries}/{LAYOUT_MAX_RETRY_LOOPS})...")
                            
                            # Save previous slide_and_script for incremental updates
                            session.state["previous_slide_and_script"] = slide_and_script
                            
                            # Compress layout review for retry (keep all details for all issue types)
                            compressed_layout_review = {
                                "overall_quality": overall_quality,
                                "passed": passed,
                                "total_issues": total_issues,
                                "overlaps_detected": issues_summary.get("overlaps_detected", 0) if isinstance(issues_summary, dict) else 0,
                                "issues": []
                            }
                            
                            # Keep all issues with all details
                            if layout_review.get("issues"):
                                for slide_issue in layout_review.get("issues", []):
                                    slide_number = slide_issue.get("slide_number")
                                    for issue in slide_issue.get("issues", []):
                                        compressed_layout_review["issues"].append({
                                            "slide_number": slide_number,
                                            "type": issue.get("type"),
                                            "severity": issue.get("severity", "minor"),
                                            "count": issue.get("count", 1),
                                            "details": issue.get("details", []),  # Keep ALL details
                                        })
                            
                            # Regenerate slides with layout feedback
                            print("\n🎨 Regenerating Slide and Script with Layout Feedback")
                            obs_logger.start_agent_execution("SlideAndScriptGeneratorAgent", output_key="slide_and_script", retry_count=layout_retries)
                            
                            # Build retry message with layout feedback
                            style_consistency_note = """
**CRITICAL: STYLE CONSISTENCY REQUIREMENT**
If layout issues require adjusting font sizes (title, subtitle, body) or positions on one slide, you MUST apply the SAME adjustments to ALL slides to maintain visual consistency:
- If you reduce title font size on one slide due to overlap, use the SAME reduced size for ALL slides
- If you adjust title/subtitle positions, use CONSISTENT positions across ALL slides
- Maintain uniform spacing and alignment patterns across the entire presentation
- Only vary design_spec when slide type changes (title slide vs regular slide), not to fix individual issues
"""
                            
                            slide_message = f"""[PREVIOUS_LAYOUT_REVIEW]
{json.dumps(compressed_layout_review, separators=(',', ':'))}
[END_PREVIOUS_LAYOUT_REVIEW]

⚠️⚠️⚠️ MANDATORY FIX REQUIREMENT ⚠️⚠️⚠️

The layout review identified {total_issues} issue(s) that MUST be fixed. This is retry attempt {layout_retries}/{LAYOUT_MAX_RETRY_LOOPS}.

**YOU MUST FIX EVERY ISSUE BELOW:**

{detailed_feedback}

**SPECIFIC FIX INSTRUCTIONS:**
- For text overlap: REDUCE font sizes (title by 4-6pt, subtitle by 2-4pt, body by 1-2pt) and INCREASE vertical spacing by at least 8-12%
- For overflow: REDUCE font sizes and/or reduce content (remove least important bullet points)
- For spacing: INCREASE spacing.title_to_subtitle by 20-30pt and spacing.subtitle_to_content by 15-25pt
- Apply fixes consistently across ALL slides of the same type

{style_consistency_note}

**VERIFICATION:** After generating, verify that:
1. Each slide_number mentioned above has been fixed
2. Overlapping words/elements are now separated by at least 10% vertical space
3. Font sizes have been reduced appropriately
4. Spacing has been increased appropriately

FAILURE TO FIX THESE ISSUES WILL RESULT IN REJECTION."""
                            
                            # Re-run slide generator with feedback
                            runner = InMemoryRunner(agent=slide_and_script_generator_agent)
                            events = await runner.run_debug(
                                f"Generate slides and script based on:\nOutline: {json.dumps(presentation_outline, separators=(',', ':'))}\nReport Knowledge: {json.dumps(report_knowledge, separators=(',', ':'))}\n\n{slide_message}",
                                session_id=session.id
                            )
                            slide_and_script = extract_output_from_events(events, "slide_and_script")
                            
                            if not slide_and_script:
                                obs_logger.finish_agent_execution(AgentStatus.FAILED, "No slide_and_script generated on retry", has_output=False)
                                print(f"⚠️  Failed to regenerate slides. Proceeding with previous version.")
                                outputs["layout_review"] = layout_review
                                break
                            
                            # Parse slide_and_script if string
                            if isinstance(slide_and_script, str):
                                try:
                                    cleaned = slide_and_script.strip()
                                    if cleaned.startswith("```json"):
                                        cleaned = cleaned[7:].lstrip()
                                    elif cleaned.startswith("```"):
                                        cleaned = cleaned[3:].lstrip()
                                    if cleaned.endswith("```"):
                                        cleaned = cleaned[:-3].rstrip()
                                    slide_and_script = json.loads(cleaned)
                                except json.JSONDecodeError as e:
                                    print(f"⚠️  Warning: Could not parse regenerated slide_and_script as JSON: {e}")
                                    outputs["layout_review"] = layout_review
                                    break
                            
                            # Re-export slides
                            print("\n📤 Re-exporting Slides to Google Slides")
                            obs_logger.start_agent_execution("SlidesExportAgent", output_key="slides_export_result", retry_count=layout_retries)
                            
                            slide_deck = slide_and_script.get("slide_deck")
                            presentation_script = slide_and_script.get("presentation_script")
                            
                            # Generate charts ONLY if chart_data is missing or invalid (not on every retry)
                            if slide_deck:
                                slides_needing_charts = []
                                for slide in slide_deck.get('slides', []):
                                    visual_elements = slide.get('visual_elements', {})
                                    if visual_elements.get('charts_needed', False) and visual_elements.get('chart_spec'):
                                        chart_data = visual_elements.get('chart_data')
                                        # Check if chart_data is missing or invalid
                                        is_invalid = (
                                            not chart_data or
                                            chart_data == "PLACEHOLDER_CHART_DATA" or
                                            (isinstance(chart_data, str) and len(chart_data) < 100)
                                        )
                                        if is_invalid:
                                            slides_needing_charts.append(slide.get('slide_number'))
                                
                                if slides_needing_charts:
                                    print(f"   📊 Regenerating charts for {len(slides_needing_charts)} slide(s) with invalid/missing chart_data: {slides_needing_charts}")
                                    chart_input = json.dumps({"slide_deck": slide_deck}, separators=(',', ':'))
                                    runner = InMemoryRunner(agent=chart_generator_agent)
                                    chart_events = await runner.run_debug(
                                        chart_input,
                                        session_id=session.id
                                    )
                                    # Get updated slide_deck from session.state
                                    updated_slide_deck = session.state.get("slide_deck") or slide_deck
                                    slide_deck = updated_slide_deck
                                else:
                                    print(f"   ℹ️  Charts are already generated, skipping chart generation in retry")
                            
                            if slide_deck and presentation_script:
                                config_dict = {
                                    'scenario': config.scenario,
                                    'duration': config.duration,
                                    'target_audience': config.target_audience,
                                    'custom_instruction': config.custom_instruction
                                }
                                
                                export_result = export_slideshow_tool(
                                    slide_deck=slide_deck,
                                    presentation_script=presentation_script,
                                    config=config_dict,
                                    title=""
                                )
                                
                                if export_result.get('status') in ['success', 'partial_success']:
                                    session.state["slideshow_export_result"] = export_result
                                    obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
                                    print(f"✅ Slides re-exported successfully")
                                    # Continue loop to review again
                                    continue
                                else:
                                    obs_logger.finish_agent_execution(AgentStatus.FAILED, "Re-export failed", has_output=False)
                                    print(f"⚠️  Failed to re-export slides. Proceeding with previous version.")
                                    outputs["layout_review"] = layout_review
                                    break
                            else:
                                obs_logger.finish_agent_execution(AgentStatus.FAILED, "Missing slide_deck or presentation_script", has_output=False)
                                print(f"⚠️  Missing slide_deck or presentation_script. Proceeding with previous version.")
                                outputs["layout_review"] = layout_review
                                break
                    else:
                        obs_logger.finish_agent_execution(AgentStatus.FAILED, "Failed to extract/parse layout review from agent output", has_output=False)
                        print(f"⚠️  Layout review not found or invalid - failed to extract/parse JSON from agent output")
                        if layout_retries >= LAYOUT_MAX_RETRY_LOOPS:
                            break
                        layout_retries += 1
                        continue
                else:
                    obs_logger.finish_agent_execution(AgentStatus.FAILED, "No shareable URL available", has_output=False)
                    print(f"⚠️  No shareable URL available for layout review")
                    break
                    
        # Save complete output
        if len(outputs) > 1:
            save_json_output(outputs, f"{output_dir}/complete_output.json")
            print(f"\n💡 Saved combined output with {len(outputs)} agent outputs.")
        
        obs_logger.finish_pipeline(save_trace=True)
        
        print("\n" + "=" * 60)
        print("🎉 Pipeline completed successfully!")
        print("=" * 60)
        print(f"\nGenerated outputs saved to '{output_dir}/' directory")
        print(f"Total outputs: {len(outputs)}")
        
        return outputs
        
    except Exception as e:
        error_msg = str(e)
        obs_logger.finish_pipeline(save_trace=True)
        print(f"\n❌ Pipeline failed with error: {error_msg}")
        raise


async def main():
    """Main function for local development."""
    # Clean up any previous logs (both old root location and new location)
    output_dir = "presentation_agent/output"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    for log_file in ["logger.log", "web.log", "tunnel.log", "observability.log"]:
        # Clean up old root location
        if os.path.exists(log_file):
            os.remove(log_file)
            print(f"🧹 Cleaned up {log_file}")
        # Clean up new location
        new_log_path = f"{output_dir}/{log_file}"
        if os.path.exists(new_log_path):
            os.remove(new_log_path)
            print(f"🧹 Cleaned up {new_log_path}")

    # Configure logging with DEBUG log level.
    logging.basicConfig(
        filename=f"{output_dir}/logger.log",
        level=logging.DEBUG,
        format="%(filename)s:%(lineno)s %(levelname)s:%(message)s",
    )

    print("✅ Logging configured")
    
    # Try to load from .env file if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # python-dotenv not installed, skip .env loading
        pass
    except Exception as e:
        print(f"Warning: Could not load .env file: {e}")
    
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("\n❌ GOOGLE_API_KEY environment variable not set")
        print("\nTo set the API key, use one of these methods:")
        print("1. Environment variable: export GOOGLE_API_KEY='your-key-here'")
        print("2. .env file: Create a .env file with: GOOGLE_API_KEY=your-key-here")
        print("   (Install python-dotenv: pip install python-dotenv)")
        print("3. Direct in code: os.environ['GOOGLE_API_KEY'] = 'your-key-here'")
        return
    
    # Example configuration
    # Note: target_audience is optional - if not provided (or set to None), LLM will infer from scenario and report
    config = PresentationConfig(
        # scenario="academic_teaching",
        duration="1 minute",
        # target_audience="students",  # Optional - can be None to let LLM infer from scenario and report content
        custom_instruction="add a chart to the experiment slide page",
        report_url="https://arxiv.org/pdf/2511.08597",
        style_images=[],  # Add image URLs here if you have them
    )
    
    try:
        # Run pipeline
        outputs = await run_presentation_pipeline(
            config=config,
            output_dir=output_dir,
            include_critics=True,
            save_intermediate=True,
            open_browser=True,  # Open Google Slides in browser after generation
        )
        
        print("\n" + "=" * 60)
        print("🎉 Pipeline completed successfully!")
        print("=" * 60)
        print(f"\nGenerated outputs saved to '{output_dir}/' directory")
        print(f"Total outputs: {len(outputs)}")
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline aborted by user (KeyboardInterrupt)")
        raise
    except Exception as e:
        print(f"\n\n❌ Pipeline failed with error: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
        # Exit gracefully
        exit(0)
