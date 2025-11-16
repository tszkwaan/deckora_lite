"""
Main script for local development and testing of the presentation generation pipeline.
"""

import os
import asyncio
import json
import datetime
import re
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

from config import PresentationConfig
from agents.orchestrator import create_presentation_pipeline, create_simple_pipeline
from agents.report_understanding import create_report_understanding_agent
from agents.outline_generator import create_outline_generator_agent
from agents.critic import create_outline_critic
from agents.slide_generator import create_slide_generator_agent
from agents.script_generator import create_script_generator_agent
from agents.slideshow_exporter import create_slideshow_exporter_agent
from agents.layout_critic import create_layout_critic_agent
from utils.pdf_loader import load_pdf
from utils.helpers import extract_output_from_events, save_json_output, preview_json
from utils.quality_check import check_outline_quality, create_quality_log_entry
from config import OUTLINE_MAX_RETRY_LOOPS, LAYOUT_MAX_RETRY_LOOPS


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
    output_dir: str = "output",
    include_critics: bool = True,
    save_intermediate: bool = True,
):
    """
    Run the complete presentation generation pipeline.
    
    Args:
        config: PresentationConfig object with all configuration
        output_dir: Directory to save outputs
        include_critics: Whether to include critic agents
        save_intermediate: Whether to save intermediate outputs
        
    Returns:
        Dictionary with all generated outputs
    """
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Load PDF if URL provided
    if config.report_url and not config.report_content:
        print(f"📄 Loading PDF from URL: {config.report_url}")
        config.report_content = load_pdf(report_url=config.report_url)
        print(f"✅ Loaded {len(config.report_content)} characters")
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="presentation_agent",
        user_id="user"
    )
    
    # Set up session state
    session.state.update(config.to_dict())
    
    # Create pipeline
    print("🔧 Creating presentation pipeline...")
    if include_critics:
        pipeline = create_presentation_pipeline(include_critics=True)
    else:
        pipeline = create_simple_pipeline(without_critics=True)
    print("✅ Pipeline created")
    
    # Create runner
    runner = InMemoryRunner(agent=pipeline)
    
    # Build initial message with explicit presentation config to prevent hallucination
    # TARGET_AUDIENCE is optional - if not provided, LLM will infer it
    target_audience_section = f"[TARGET_AUDIENCE]\n{config.target_audience}\n" if config.target_audience else "[TARGET_AUDIENCE]\nN/A\n"
    
    initial_message = f"""
[SCENARIO]
{config.scenario}

[DURATION]
{config.duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{config.custom_instruction}

[REPORT_URL]
{config.report_url or 'N/A'}

[REPORT_CONTENT]
{config.report_content}
[END_REPORT_CONTENT]

Your task:
- Use ONLY the above information.
- Produce the required `report_knowledge` JSON.
- Do NOT ask any questions.
- Do NOT invent information not in the report_content.
- Use the scenario, duration, and custom_instruction to guide your analysis.
- If TARGET_AUDIENCE is "N/A", infer it from the scenario and report content.
"""
    
    # Run pipeline - first get report knowledge
    print("\n🚀 Starting pipeline execution...")
    print("=" * 60)
    
    # Step 1: Generate report knowledge (no retry needed)
    report_knowledge_agent = create_report_understanding_agent()
    report_runner = InMemoryRunner(agent=report_knowledge_agent)
    report_events = await report_runner.run_debug(initial_message, session_id=session.id)
    
    # Extract report_knowledge
    outputs = {}
    report_knowledge = extract_output_from_events(report_events, "report_knowledge")
    if report_knowledge:
        outputs["report_knowledge"] = report_knowledge
        session.state["report_knowledge"] = report_knowledge
        if save_intermediate:
            output_file = f"{output_dir}/report_knowledge.json"
            save_json_output(report_knowledge, output_file)
            print(f"📄 Report knowledge saved to: {output_file}")
            print(f"\nPreview:\n{preview_json(report_knowledge)}\n")
    else:
        print("⚠️  Warning: No report_knowledge found in pipeline output")
        return outputs
    
    # Step 2: Generate outline with quality check and retry loop
    print("\n" + "=" * 60)
    print("🔄 Starting outline generation with quality checks...")
    print("=" * 60)
    
    outline_generator = create_outline_generator_agent()
    outline_critic = create_outline_critic()
    outline_runner = InMemoryRunner(agent=outline_generator)
    critic_runner = InMemoryRunner(agent=outline_critic)
    
    quality_logs = []
    outline = None
    outline_review = None
    
    for attempt in range(1, OUTLINE_MAX_RETRY_LOOPS + 1):
        print(f"\n📝 Attempt {attempt}/{OUTLINE_MAX_RETRY_LOOPS}: Generating outline...")
        
        # Build outline generator message with explicit data to prevent hallucination
        report_knowledge_json = json.dumps(report_knowledge, indent=2, ensure_ascii=False)
        target_audience_section = f"[TARGET_AUDIENCE]\n{config.target_audience or 'N/A'}\n" if config.target_audience else "[TARGET_AUDIENCE]\nN/A\n"
        
        outline_message = f"""
[REPORT_KNOWLEDGE]
{report_knowledge_json}
[END_REPORT_KNOWLEDGE]

[SCENARIO]
{config.scenario}

[DURATION]
{config.duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{config.custom_instruction}

Your task:
- Generate a presentation outline based ONLY on the [REPORT_KNOWLEDGE] provided above.
- Use the scenario, duration, and custom_instruction to guide structure and focus.
- Do NOT invent any facts, numbers, or technical details not in the report_knowledge.
- All content must be traceable to report_knowledge sections.
- Output the outline as JSON in the required format.
- Do NOT ask any questions - all data is provided above.
"""
        
        # Generate outline
        outline_events = await outline_runner.run_debug(outline_message, session_id=session.id)
        outline = extract_output_from_events(outline_events, "presentation_outline")
        
        if not outline:
            print(f"⚠️  Warning: No outline generated in attempt {attempt}")
            continue
        
        # Update session state with outline (for other agents that might need it)
        session.state["presentation_outline"] = outline
        
        # Run critic - pass outline and report_knowledge directly in message
        print(f"🔍 Running quality check (attempt {attempt})...")
        
        # Build critic message with explicit data
        outline_json = json.dumps(outline, indent=2, ensure_ascii=False)
        report_knowledge_json = json.dumps(report_knowledge, indent=2, ensure_ascii=False)
        
        target_audience_section = f"[TARGET_AUDIENCE]\n{config.target_audience or 'N/A'}\n" if config.target_audience else "[TARGET_AUDIENCE]\nN/A\n"
        
        critic_message = f"""
[PRESENTATION_OUTLINE]
{outline_json}
[END_PRESENTATION_OUTLINE]

[REPORT_KNOWLEDGE]
{report_knowledge_json}
[END_REPORT_KNOWLEDGE]

[SCENARIO]
{config.scenario}

[DURATION]
{config.duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{config.custom_instruction}

Your task:
- Review the presentation outline using the provided data above.
- Perform hallucination check by comparing outline against report_knowledge.
- Perform safety check for violations.
- Output the review as JSON in the required format.
- Do NOT ask any questions - all data is provided above.
"""
        
        critic_events = await critic_runner.run_debug(critic_message, session_id=session.id)
        outline_review = extract_output_from_events(critic_events, "critic_review_outline")
        
        if not outline_review:
            print(f"⚠️  Warning: No critic review generated in attempt {attempt}")
            # Continue to next attempt
            continue
        
        # Debug: print the type of outline_review to help diagnose
        if isinstance(outline_review, str):
            print(f"   ⚠️  Note: Critic review is a string, will attempt to parse as JSON")
            print(f"   First 200 chars: {outline_review[:200]}...")
        
        # Check quality
        passed, details = check_outline_quality(outline_review)
        
        # Print more details if quality check failed
        if not passed and details.get("error"):
            print(f"   ⚠️  Quality check error: {details.get('error')}")
            print(f"   Review type: {type(outline_review).__name__}")
            if isinstance(outline_review, dict):
                print(f"   Available keys: {list(outline_review.keys())[:10]}")
        log_entry = create_quality_log_entry(attempt, passed, details, OUTLINE_MAX_RETRY_LOOPS)
        log_entry["timestamp"] = datetime.datetime.now().isoformat()
        quality_logs.append(log_entry)
        
        print(f"\n📊 Quality Check Results (Attempt {attempt}):")
        print(f"   Hallucination Score: {details.get('hallucination_score', 'N/A')} (threshold: {details.get('hallucination_threshold', 'N/A')})")
        print(f"   Safety Score: {details.get('safety_score', 'N/A')} (threshold: {details.get('safety_threshold', 'N/A')})")
        print(f"   Status: {'✅ PASSED' if passed else '❌ FAILED'}")
        
        if passed:
            print(f"\n✅ Outline quality check passed on attempt {attempt}!")
            # Ensure outline is preserved after break
            if not outline:
                print(f"   ⚠️  CRITICAL: Outline became None after passing critic!")
            break
        else:
            if attempt < OUTLINE_MAX_RETRY_LOOPS:
                print(f"\n⚠️  Quality check failed. Retrying... ({attempt}/{OUTLINE_MAX_RETRY_LOOPS})")
                for reason in details.get("failure_reasons", []):
                    print(f"   - {reason}")
                # Don't reset outline - keep it for next attempt
            else:
                print(f"\n⚠️  WARNING: Maximum retry attempts ({OUTLINE_MAX_RETRY_LOOPS}) reached.")
                print(f"   Proceeding with outline despite quality issues.")
                for reason in details.get("failure_reasons", []):
                    print(f"   - {reason}")
                # Keep the outline from the last attempt
        break
    
    print("=" * 60)
    print("✅ Outline generation complete\n")
    
    # Debug: Check outline status - this should ALWAYS be available if critic passed
    if outline:
        print(f"✅ Outline is available (type: {type(outline).__name__})")
        if isinstance(outline, dict):
            print(f"   Outline keys: {list(outline.keys())[:10]}")
            print(f"   Number of slides in outline: {len(outline.get('slides', []))}")
    else:
        print(f"⚠️  WARNING: Outline is None or empty after generation loop!")
        print(f"   This should NOT happen if critic passed - check for errors above.")
        print(f"   This will skip slide generation.")
    
    # Save outline and review
    if outline:
        outputs["presentation_outline"] = outline
        if save_intermediate:
            output_file = f"{output_dir}/presentation_outline.json"
            save_json_output(outline, output_file)
            print(f"📄 Presentation outline saved to: {output_file}")
            print(f"\nPreview:\n{preview_json(outline)}\n")
    else:
        print("⚠️  WARNING: Cannot save outline - outline is None or empty")
    
    if outline_review:
        outputs["outline_review"] = outline_review
        if save_intermediate:
            output_file = f"{output_dir}/outline_review.json"
            save_json_output(outline_review, output_file)
            print(f"📄 Outline review saved to: {output_file}")
            print(f"\nPreview:\n{preview_json(outline_review)}\n")
    
    # Save quality logs
    if quality_logs:
        outputs["quality_logs"] = quality_logs
        if save_intermediate:
            log_file = f"{output_dir}/quality_logs.json"
            save_json_output(quality_logs, log_file)
            print(f"📊 Quality logs saved to: {log_file}")
            
            # Print summary
            final_log = quality_logs[-1]
            if final_log.get("status") == "max_loops_reached":
                print(f"\n⚠️  WARNING: {final_log.get('warning', '')}")
    
    # Step 3 & 4: Generate slide deck, script, export, and layout review with retry loop
    if outline:
        slide_deck = None
        script = None
        layout_review = None
        previous_layout_feedback = None
        
        for layout_attempt in range(1, LAYOUT_MAX_RETRY_LOOPS + 1):
            print("\n" + "=" * 60)
            if layout_attempt > 1:
                print(f"🔄 Slide Generation Retry Loop (Attempt {layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                print("=" * 60)
                if previous_layout_feedback:
                    print("\n📋 Previous Layout Review Feedback:")
                    issues_summary = previous_layout_feedback.get("issues_summary", {})
                    total_issues = issues_summary.get("total_issues", 0)
                    print(f"   Total issues found: {total_issues}")
                    if previous_layout_feedback.get("issues"):
                        print(f"   Issues on {len(previous_layout_feedback['issues'])} slides")
                        # Show specific feedback
                        for slide_issue in previous_layout_feedback["issues"][:3]:  # Show first 3
                            slide_num = slide_issue.get("slide_number", "?")
                            for issue in slide_issue.get("issues", []):
                                issue_type = issue.get("type", "unknown")
                                count = issue.get("count", 0)
                                print(f"   - Slide {slide_num}: {issue_type} ({count} instances)")
            else:
                print("🎨 Starting slide generation...")
                print("=" * 60)
            
            # Step 3a: Generate slide deck
            slide_generator = create_slide_generator_agent()
            slide_runner = InMemoryRunner(agent=slide_generator)
            
            # Build slide generator message
            outline_json = json.dumps(outline, indent=2, ensure_ascii=False)
            report_knowledge_json = json.dumps(report_knowledge, indent=2, ensure_ascii=False)
            target_audience_section = f"[TARGET_AUDIENCE]\n{config.target_audience or 'N/A'}\n" if config.target_audience else "[TARGET_AUDIENCE]\nN/A\n"
            
            # Add layout feedback if this is a retry
            layout_feedback_section = ""
            if previous_layout_feedback and layout_attempt > 1:
                layout_feedback_json = json.dumps(previous_layout_feedback, indent=2, ensure_ascii=False)
                layout_feedback_section = f"""
[PREVIOUS_LAYOUT_REVIEW]
{layout_feedback_json}
[END_PREVIOUS_LAYOUT_REVIEW]

IMPORTANT: The previous slide generation had layout issues. Please address:
- Text overlap issues: Ensure titles and content don't overlap
- Title length: Keep titles short (max 2 lines) and use smaller font sizes
- Content spacing: Ensure proper spacing between text elements
- Follow the layout feedback above to improve slide formatting
"""
            
            slide_message = f"""
[PRESENTATION_OUTLINE]
{outline_json}
[END_PRESENTATION_OUTLINE]

[REPORT_KNOWLEDGE]
{report_knowledge_json}
[END_REPORT_KNOWLEDGE]

[SCENARIO]
{config.scenario}

[DURATION]
{config.duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{config.custom_instruction}
{layout_feedback_section}
Your task:
- Generate detailed slide content based ONLY on the [PRESENTATION_OUTLINE] and [REPORT_KNOWLEDGE] provided above.
- Use the scenario, duration, and custom_instruction to guide the slide content.
- Do NOT invent any facts, numbers, or technical details not in the report_knowledge.
- All content must be traceable to report_knowledge sections.
- Output the slide deck as JSON in the required format.
- Do NOT ask any questions - all data is provided above.
"""
            
            print("📝 Generating slide deck...")
            slide_events = await slide_runner.run_debug(slide_message, session_id=session.id)
            slide_deck = extract_output_from_events(slide_events, "slide_deck")
            
            # Parse slide_deck if it's a string (JSON wrapped in markdown)
            if slide_deck and isinstance(slide_deck, str):
                try:
                    cleaned = slide_deck.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:].lstrip()
                    elif cleaned.startswith("```"):
                        cleaned = cleaned[3:].lstrip()
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3].rstrip()
                    slide_deck = json.loads(cleaned)
                    print(f"📊 Debug: Parsed slide_deck from string to dict")
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"⚠️  Warning: Could not parse slide_deck as JSON: {e}")
                    slide_deck = None
            
            if not slide_deck:
                print("⚠️  Warning: No slide_deck found in pipeline output")
                print("   Slide generation may have failed - check agent output above")
                if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                    print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                    continue
                else:
                    print("   Max retries reached. Continuing without slide deck.")
                    break
            
            outputs["slide_deck"] = slide_deck
            session.state["slide_deck"] = slide_deck
            if save_intermediate:
                output_file = f"{output_dir}/slide_deck.json"
                save_json_output(slide_deck, output_file)
                print(f"📄 Slide deck saved to: {output_file}")
                print(f"\nPreview:\n{preview_json(slide_deck)}\n")
            print(f"✅ Slide deck generated successfully ({len(slide_deck.get('slides', []))} slides)")
            
            # Step 3b: Generate presentation script
            print("\n" + "=" * 60)
            print("📝 Starting script generation...")
            print("=" * 60)
            
            script_generator = create_script_generator_agent()
            script_runner = InMemoryRunner(agent=script_generator)
            
            # Build script generator message
            slide_deck_json = json.dumps(slide_deck, indent=2, ensure_ascii=False)
            report_knowledge_json = json.dumps(report_knowledge, indent=2, ensure_ascii=False)
            target_audience_section = f"[TARGET_AUDIENCE]\n{config.target_audience or 'N/A'}\n" if config.target_audience else "[TARGET_AUDIENCE]\nN/A\n"
            
            # Parse target duration to seconds for validation
            target_duration_seconds = parse_duration_to_seconds(config.duration)
            
            script_message = f"""
[SLIDE_DECK]
{slide_deck_json}
[END_SLIDE_DECK]

[REPORT_KNOWLEDGE]
{report_knowledge_json}
[END_REPORT_KNOWLEDGE]

[SCENARIO]
{config.scenario}

[DURATION]
{config.duration}
Target duration in seconds: {target_duration_seconds}

{target_audience_section}[CUSTOM_INSTRUCTION]
{config.custom_instruction}

Your task:
- Generate a detailed presentation script based on the [SLIDE_DECK] provided above.
- Use [REPORT_KNOWLEDGE] for detailed technical content and explanations.
- Expand on slide content with detailed explanations (especially important given: "{config.custom_instruction}").
- Include smooth transitions between slides.
- CRITICAL: Ensure the total_estimated_time in script_metadata matches the target duration ({config.duration} = {target_duration_seconds} seconds).
- Each point in main_content should have an estimated_time in seconds.
- Sum of all estimated_time values should approximately equal {target_duration_seconds} seconds.
- Output the script as JSON in the required format.
- Do NOT ask any questions - all data is provided above.
"""
            
            print("📝 Generating presentation script...")
            script_events = await script_runner.run_debug(script_message, session_id=session.id)
            script = extract_output_from_events(script_events, "presentation_script")
            
            # Parse script if it's a string (JSON wrapped in markdown)
            if script and isinstance(script, str):
                try:
                    cleaned = script.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:].lstrip()
                    elif cleaned.startswith("```"):
                        cleaned = cleaned[3:].lstrip()
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3].rstrip()
                    script = json.loads(cleaned)
                    print(f"📊 Debug: Parsed script from string to dict")
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"⚠️  Warning: Could not parse script as JSON: {e}")
                    script = None
            
            if not script:
                print("⚠️  Warning: No presentation_script found in pipeline output")
                if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                    print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                    continue
                else:
                    print("   Max retries reached. Continuing without script.")
                    break
            
            # Ensure script is a dict before accessing
            if not isinstance(script, dict):
                print(f"⚠️  Warning: script is not a dict (type: {type(script).__name__})")
                if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                    print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                    continue
                else:
                    print("   Max retries reached. Continuing without script.")
                    break
            
            # Validate estimated time matches target duration
            script_metadata = script.get("script_metadata", {})
            estimated_time_str = script_metadata.get("total_estimated_time", "")
            
            # Try to parse estimated time
            estimated_seconds = None
            if estimated_time_str:
                # Try to extract seconds from string like "1200 seconds" or "20 minutes"
                estimated_seconds = parse_duration_to_seconds(estimated_time_str)
            else:
                # Calculate from individual point times if available
                total_seconds = 0
                for section in script.get("script_sections", []):
                    for point in section.get("main_content", []):
                        point_time = point.get("estimated_time", 0)
                        if isinstance(point_time, (int, float)):
                            total_seconds += point_time
                        elif isinstance(point_time, str):
                            try:
                                total_seconds += int(point_time)
                            except:
                                pass
                if total_seconds > 0:
                    estimated_seconds = total_seconds
            
            # Check if time matches (allow 10% tolerance)
            if estimated_seconds:
                time_diff = abs(estimated_seconds - target_duration_seconds)
                tolerance = target_duration_seconds * 0.1  # 10% tolerance
                
                if time_diff > tolerance:
                    print(f"\n⚠️  WARNING: Script timing mismatch!")
                    print(f"   Target duration: {config.duration} ({target_duration_seconds} seconds)")
                    print(f"   Estimated duration: {estimated_time_str} ({estimated_seconds} seconds)")
                    print(f"   Difference: {time_diff} seconds ({time_diff/target_duration_seconds*100:.1f}% off)")
                    print(f"   Consider adjusting the script length to match the target duration.")
                else:
                    print(f"\n✅ Script timing validated: {estimated_seconds}s matches target {target_duration_seconds}s (within tolerance)")
            else:
                print(f"\n⚠️  WARNING: Could not parse estimated time from script. Please verify manually.")
            
            outputs["presentation_script"] = script
            session.state["presentation_script"] = script
            if save_intermediate:
                output_file = f"{output_dir}/presentation_script.json"
                save_json_output(script, output_file)
                print(f"📄 Presentation script saved to: {output_file}")
                print(f"\nPreview:\n{preview_json(script)}\n")
            
            print("=" * 60)
            print("✅ Script generation complete\n")
            
            # Step 3c: Export to Google Slides (call tool directly to avoid MALFORMED_FUNCTION_CALL)
            try:
                print("\n" + "=" * 60)
                print("📊 Exporting to Google Slides...")
                print("=" * 60)
                
                # Call the tool directly instead of using agent to avoid MALFORMED_FUNCTION_CALL
                # The agent was failing because the parameters are too large for ADK to handle
                from tools.google_slides_tool import export_slideshow_tool
                
                print("📝 Calling export_slideshow_tool directly...")
                print("   (This may take a while - creating Google Slides presentation)")
                
                export_result = export_slideshow_tool(
                    slide_deck=slide_deck,
                    presentation_script=script,
                    config=config.to_dict(),
                    title=""
                )
                
                print(f"✅ Tool call completed")
                
                # The tool directly returns the result dict - no need to extract from events
                # export_result is already set from the tool call above
                
                # Handle nested result structure
                if isinstance(export_result, dict) and "slideshow_export_result" in export_result:
                    export_result = export_result["slideshow_export_result"]
                
                # Ensure export_result is a dict (parse JSON string if needed)
                if export_result and isinstance(export_result, str):
                    try:
                        # Strip markdown code blocks if present
                        cleaned = export_result.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:].lstrip()
                        elif cleaned.startswith("```"):
                            cleaned = cleaned[3:].lstrip()
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3].rstrip()
                        export_result = json.loads(cleaned)
                        print(f"📊 Debug: Parsed export_result from string to dict")
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"⚠️  Warning: Could not parse export_result as JSON: {e}")
                        export_result = None
                
                # Final check: if we have a dict with presentation_id, accept it even without status="success"
                if export_result and isinstance(export_result, dict):
                    # Check if we have a valid result (either status="success" or presentation_id present)
                    if export_result.get("status") == "success" or export_result.get("presentation_id"):
                        # Success! Normalize the result format
                        if not export_result.get("status"):
                            export_result["status"] = "success"
                        if not export_result.get("message"):
                            export_result["message"] = "Google Slides presentation created successfully"
                        
                        presentation_id = export_result.get("presentation_id")
                        shareable_url = export_result.get("shareable_url")
                        
                        if presentation_id:
                            # Save IDs to files
                            id_file = f"{output_dir}/presentation_slides_id.txt"
                            url_file = f"{output_dir}/presentation_slides_url.txt"
                            
                            with open(id_file, 'w') as f:
                                f.write(presentation_id)
                            with open(url_file, 'w') as f:
                                f.write(shareable_url)
                            
                            print(f"\n✅ Google Slides export successful!")
                            print(f"   Presentation ID: {presentation_id}")
                            print(f"   Shareable URL: {shareable_url}")
                            print(f"\n📄 Presentation ID saved to: {id_file}")
                            print(f"📄 Shareable URL saved to: {url_file}")
                            
                            outputs["slideshow_export_result"] = export_result
                            
                            # Step 3d: Layout review with Vision API
                            if presentation_id:
                                print("\n" + "=" * 60)
                                print("🔍 Reviewing slide layout...")
                                print("=" * 60)
                                
                                try:
                                    # Create layout critic agent
                                    layout_critic = create_layout_critic_agent()
                                    layout_runner = InMemoryRunner(agent=layout_critic)
                                    
                                    # Build message for layout critic
                                    layout_message = f"""
[PRESENTATION_ID]
{presentation_id}
[END_PRESENTATION_ID]

[OUTPUT_DIR]
{output_dir}
[END_OUTPUT_DIR]

Your task:
- Use the review_layout_tool to analyze the Google Slides presentation
- Pass output_dir={output_dir} to save PDFs to {output_dir}/pdf/
- The tool will export slides as images and analyze them with Vision API
- Review the results and provide feedback on layout issues
- Return the review as JSON in the required format
"""
                                    
                                    print("📝 Running layout critic agent...")
                                    layout_events = await layout_runner.run_debug(layout_message, session_id=session.id)
                                    
                                    # Extract layout review
                                    layout_review = extract_output_from_events(layout_events, "layout_review")
                                    
                                    # Handle nested result structure
                                    if isinstance(layout_review, dict) and "layout_review" in layout_review:
                                        layout_review = layout_review["layout_review"]
                                    
                                    # Ensure layout_review is a dict (parse JSON string if needed)
                                    if layout_review and isinstance(layout_review, str):
                                        try:
                                            # Strip markdown code blocks if present
                                            cleaned = layout_review.strip()
                                            if cleaned.startswith("```json"):
                                                cleaned = cleaned[7:].lstrip()
                                            elif cleaned.startswith("```"):
                                                cleaned = cleaned[3:].lstrip()
                                            if cleaned.endswith("```"):
                                                cleaned = cleaned[:-3].rstrip()
                                            # Try to parse as JSON
                                            layout_review = json.loads(cleaned)
                                            print(f"📊 Debug: Parsed layout_review from string to dict")
                                        except (json.JSONDecodeError, ValueError) as e:
                                            print(f"⚠️  Warning: Could not parse layout_review as JSON: {e}")
                                            print(f"   Raw string (first 500 chars): {layout_review[:500]}")
                                            # Try to extract JSON from the string if it contains escaped quotes
                                            try:
                                                # Sometimes the JSON is wrapped in quotes or has escaped quotes
                                                # Try to unescape and parse again
                                                import ast
                                                unescaped = ast.literal_eval(f'"{cleaned}"') if cleaned.startswith('"') and cleaned.endswith('"') else cleaned
                                                layout_review = json.loads(unescaped)
                                                print(f"📊 Debug: Parsed layout_review after unescaping")
                                            except:
                                                layout_review = None
                                    
                                    if layout_review and isinstance(layout_review, dict):
                                        # Check if there's an error in the review
                                        if layout_review.get("error"):
                                            error_msg = layout_review.get("error", "Unknown error")
                                            print(f"\n⚠️  Layout review tool error: {error_msg}")
                                            # If it's a dependency error, break (don't retry)
                                            if "pdf2image" in error_msg.lower() or "poppler" in error_msg.lower():
                                                print("   This is a dependency issue. Please install required packages.")
                                                break
                                            # For other errors, continue to retry logic
                                            if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                                                print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                                            else:
                                                print(f"   Max retries reached. Continuing without layout review.")
                                                break
                                            continue
                                        
                                        # Check if layout review passed
                                        passed = layout_review.get("passed", False)
                                        overall_quality = layout_review.get("overall_quality", "unknown")
                                        issues_summary = layout_review.get("issues_summary", {})
                                        issues_count = issues_summary.get("total_issues", 0) if isinstance(issues_summary, dict) else 0
                                        
                                        if passed:
                                            print(f"\n✅ Layout review passed!")
                                            print(f"   Overall quality: {overall_quality}")
                                            print(f"\n✅ Slide generation and layout review complete!")
                                            # Break out of retry loop - success!
                                            break
                                        else:
                                            print(f"\n⚠️  Layout review found issues!")
                                            print(f"   Overall quality: {overall_quality}")
                                            print(f"   Total issues: {issues_count}")
                                            if layout_review.get("issues"):
                                                print(f"   Issues found on {len(layout_review['issues'])} slides")
                                            
                                            # Store feedback for next retry
                                            previous_layout_feedback = layout_review
                                            
                                            if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                                                print(f"\n🔄 Retrying slide generation with layout feedback... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                                                # Continue to next iteration of retry loop
                                            else:
                                                print(f"\n⚠️  WARNING: Maximum retry attempts ({LAYOUT_MAX_RETRY_LOOPS}) reached.")
                                                print(f"   Proceeding with slides despite layout issues.")
                                                # Break out of retry loop - max retries reached
                                                break
                                    elif layout_review and isinstance(layout_review, str):
                                        print(f"\n⚠️  Layout review is a string (not parsed): {layout_review[:200]}")
                                        if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                                            print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                                        else:
                                            print(f"   Max retries reached. Continuing without layout review.")
                                            break
                                    else:
                                        print(f"\n⚠️  Layout review not available or invalid format")
                                        print(f"   Type: {type(layout_review).__name__ if layout_review else 'None'}")
                                        # If we can't get layout review, assume it's okay and break
                                        if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                                            print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                                        else:
                                            print(f"   Max retries reached. Continuing without layout review.")
                                            break
                                            
                                except FileNotFoundError as e:
                                    print(f"\n⚠️  Layout review skipped: {e}")
                                    print("   Vision API credentials not found. See LAYOUT_REVIEW_SETUP.md for setup.")
                                    # If Vision API not available, skip layout review and break
                                    break
                                except Exception as e:
                                    error_str = str(e)
                                    print(f"\n⚠️  Layout review failed: {error_str}")
                                    # Check if it's a dependency or parsing error
                                    if "pdf2image" in error_str.lower() or "poppler" in error_str.lower() or "'str' object has no attribute 'get'" in error_str:
                                        print("   This appears to be a dependency or parsing issue.")
                                        print("   Skipping layout review for this attempt.")
                                        if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                                            print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                                            continue
                                        else:
                                            print(f"   Max retries reached. Continuing without layout review.")
                                            break
                                    if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                                        print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                                    else:
                                        print(f"   Max retries reached. Continuing without layout review.")
                                        break
                        else:
                            # No presentation_id - export failed
                            if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                                print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                                continue
                            else:
                                print("   Max retries reached. Continuing without Google Slides export.")
                                break
                            
                else:
                    if isinstance(export_result, dict):
                        error_msg = export_result.get("error", "Unknown error")
                    elif isinstance(export_result, str):
                        error_msg = f"Export result is a string (not parsed): {export_result[:100]}"
                    else:
                        error_msg = f"Export result has unexpected type: {type(export_result).__name__}"
                    if not export_result:
                        error_msg = "No result returned"
                    print(f"\n⚠️  Google Slides export failed: {error_msg}")
                    if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                        print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                        continue
                    else:
                        print("   Max retries reached. Continuing without Google Slides export.")
                        break
                    
            except FileNotFoundError as e:
                print(f"\n⚠️  Google Slides export skipped: {e}")
                print("   See GOOGLE_SLIDES_SETUP.md for setup instructions.")
                # If credentials not available, break out of retry loop
                break
            except Exception as e:
                print(f"\n⚠️  Google Slides export failed: {e}")
                if layout_attempt < LAYOUT_MAX_RETRY_LOOPS:
                    print(f"   Retrying... ({layout_attempt}/{LAYOUT_MAX_RETRY_LOOPS})")
                    continue
                else:
                    print("   Max retries reached. Continuing without Google Slides export.")
                    break
        
        # Save layout review if available
        if layout_review:
            outputs["layout_review"] = layout_review
            if save_intermediate:
                output_file = f"{output_dir}/layout_review.json"
                save_json_output(layout_review, output_file)
                print(f"📄 Layout review saved to: {output_file}")
        
        print("=" * 60)
        print("✅ Slide generation, script, export, and layout review complete\n")
    else:
        print("⚠️  WARNING: Slide generation SKIPPED because outline is None or empty!")
        print("   Check outline generation step above for errors.")
        slide_deck = None
        script = None
    
    # Save complete output only if there are multiple outputs
    # When there's only one output, it's redundant with the individual file
    if len(outputs) > 1:
        save_json_output(outputs, f"{output_dir}/complete_output.json")
        print(f"💡 Saved combined output with {len(outputs)} agent outputs.")
    elif len(outputs) == 1:
        print(f"💡 Skipping complete_output.json (only one output - use the individual file instead).")
    
    return outputs


async def main():
    """Main function for local development."""
    # Try to load from .env file if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    except ImportError:
        # python-dotenv not installed, skip .env loading
        pass
    except Exception as e:
        print(f"⚠️  Warning: Could not load .env file: {e}")
    
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY environment variable not set")
        print("\nTo set the API key, use one of these methods:")
        print("1. Environment variable: export GOOGLE_API_KEY='your-key-here'")
        print("2. .env file: Create a .env file with: GOOGLE_API_KEY=your-key-here")
        print("   (Install python-dotenv: pip install python-dotenv)")
        print("3. Direct in code: os.environ['GOOGLE_API_KEY'] = 'your-key-here'")
        return
    
    print(f"✅ API key found (length: {len(api_key)} characters)")
    
    # Example configuration
    # Note: target_audience is optional - if not provided (or set to None), LLM will infer from scenario and report
    config = PresentationConfig(
        scenario="academic_teaching",
        duration="2 minutes",
        target_audience="students",  # Optional - can be None to let LLM infer from scenario and report content
        custom_instruction="keep the slide as clean as possible, use more point forms, keep the details in speech only",
        report_url="https://arxiv.org/pdf/2511.08597",
        style_images=[],  # Add image URLs here if you have them
    )
    
    # Run pipeline
    outputs = await run_presentation_pipeline(
        config=config,
        output_dir="output",
        include_critics=True,
        save_intermediate=True,
    )
    
    print("\n" + "=" * 60)
    print("🎉 Pipeline completed successfully!")
    print("=" * 60)
    print(f"\nGenerated outputs saved to 'output/' directory")
    print(f"Total outputs: {len(outputs)}")


if __name__ == "__main__":
    asyncio.run(main())

