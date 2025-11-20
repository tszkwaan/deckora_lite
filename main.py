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

from config import PresentationConfig
# Import individual agents for manual orchestration
from presentation_agent.agents.report_understanding_agent.agent import agent as report_understanding_agent
from presentation_agent.agents.outline_generator_agent.agent import agent as outline_generator_agent
from presentation_agent.agents.outline_critic_agent.agent import agent as outline_critic_agent
from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_and_script_generator_agent
from presentation_agent.agents.layout_critic_agent.agent import agent as layout_critic_agent

# Import tools and utilities
from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool
from presentation_agent.agents.utils.pdf_loader import load_pdf
from presentation_agent.agents.utils.helpers import extract_output_from_events, save_json_output, extract_relevant_knowledge, preview_json
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
        print(f"✅ Loaded {len(config.report_content)} characters")
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="presentation_agent",
        user_id="user"
    )
    
    # Set up session state
    session.state.update(config.to_dict())
    
    # Build initial message (same format as server.py)
    target_audience_section = (
        f"[TARGET_AUDIENCE]\n{config.target_audience}\n"
        if config.target_audience
        else "[TARGET_AUDIENCE]\nN/A\n"
    )
    
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
            # Extract only relevant knowledge for OutlineGeneratorAgent
            relevant_knowledge = extract_relevant_knowledge(report_knowledge, "OutlineGeneratorAgent")
            original_size = len(json.dumps(report_knowledge))
            filtered_size = len(json.dumps(relevant_knowledge))
            reduction = (1 - filtered_size / original_size) * 100 if original_size > 0 else 0
            print(f"📦 Context compaction: {original_size:,} → {filtered_size:,} chars ({reduction:.1f}% reduction) for OutlineGeneratorAgent")
            events = await runner.run_debug(
                f"[REPORT_KNOWLEDGE]\n{json.dumps(relevant_knowledge, indent=2)}\n[END_REPORT_KNOWLEDGE]\n\n[SCENARIO]\n{config.scenario}\n\n[DURATION]\n{config.duration}\n\n[TARGET_AUDIENCE]\n{config.target_audience or 'N/A'}\n\n[CUSTOM_INSTRUCTION]\n{config.custom_instruction}\n\nGenerate a presentation outline based on the report knowledge above.",
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
                critic_input = f"""[PRESENTATION_OUTLINE]
{json.dumps(presentation_outline, indent=2)}
[END_PRESENTATION_OUTLINE]

[REPORT_KNOWLEDGE]
{json.dumps(report_knowledge, indent=2)}
[END_REPORT_KNOWLEDGE]

[SCENARIO]
{config.scenario}

[DURATION]
{config.duration}

[TARGET_AUDIENCE]
{config.target_audience}

[CUSTOM_INSTRUCTION]
{config.custom_instruction}

Review this outline for quality, hallucination, and safety."""
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
        # Extract only relevant knowledge for SlideAndScriptGeneratorAgent (filtered by outline)
        relevant_knowledge = extract_relevant_knowledge(report_knowledge, "SlideAndScriptGeneratorAgent", presentation_outline)
        original_size = len(json.dumps(report_knowledge))
        filtered_size = len(json.dumps(relevant_knowledge))
        reduction = (1 - filtered_size / original_size) * 100 if original_size > 0 else 0
        print(f"📦 Context compaction: {original_size:,} → {filtered_size:,} chars ({reduction:.1f}% reduction) for SlideAndScriptGeneratorAgent")
        events = await runner.run_debug(
            f"[PRESENTATION_OUTLINE]\n{json.dumps(presentation_outline, indent=2)}\n[END_PRESENTATION_OUTLINE]\n\n[REPORT_KNOWLEDGE]\n{json.dumps(relevant_knowledge, indent=2)}\n[END_REPORT_KNOWLEDGE]\n\n[SCENARIO]\n{config.scenario}\n\n[DURATION]\n{config.duration}\n\n[TARGET_AUDIENCE]\n{config.target_audience or 'N/A'}\n\n[CUSTOM_INSTRUCTION]\n{config.custom_instruction}\n\nGenerate slides and script based on the outline and report knowledge above.",
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
                    import re
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
        
        # Step 5: Layout Critic (optional, if export succeeded)
        if include_critics and export_result.get('status') in ['success', 'partial_success']:
            print("\n🎨 Step 5: Layout Review")
            obs_logger.start_agent_execution("LayoutCriticAgent", output_key="layout_review")
            
            shareable_url = export_result.get("shareable_url") or f"https://docs.google.com/presentation/d/{export_result.get('presentation_id')}/edit"
            if shareable_url:
                # Store slides_export_result in session.state so agent can access it
                session.state["slides_export_result"] = export_result
                
                # Build input message with slides_export_result in the format agent expects
                layout_input = f"""The SlidesExportAgent has completed. Here is the slides_export_result:

{json.dumps(export_result, indent=2)}

Extract the shareable_url from slides_export_result and call review_layout_tool with it to review the layout."""
                
                runner = InMemoryRunner(agent=layout_critic_agent)
                events = await runner.run_debug(layout_input, session_id=session.id)
                
                # Extract layout_review - check multiple sources
                layout_review = None
                import logging
                logger = logging.getLogger(__name__)
                
                # Priority 1: Check state_delta (agent's text output stored by output_key)
                layout_review = extract_output_from_events(events, "layout_review")
                
                # Priority 2: Check tool_results directly - the tool returns the dict itself
                if not layout_review:
                    print("🔍 [DEBUG] Checking tool_results for layout_review in main.py...")
                    print(f"   Total events: {len(events)}")
                    
                    for i, event in enumerate(reversed(events)):
                        agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
                        
                        # Since we run this agent in isolation, we can check all events
                        # regardless of whether the agent name is correctly populated
                        print(f"   Event {len(events)-1-i} ({agent_name}): Checking actions...")
                        
                        if hasattr(event, 'actions') and event.actions:
                            if hasattr(event.actions, 'tool_results') and event.actions.tool_results:
                                print(f"   Found {len(event.actions.tool_results)} tool_results")
                                for j, tool_result in enumerate(event.actions.tool_results):
                                    if hasattr(tool_result, 'response'):
                                        response = tool_result.response
                                        print(f"      Result {j} type: {type(response).__name__}")
                                        
                                        # Handle string response (often JSON string)
                                        if isinstance(response, str):
                                            try:
                                                # Try to clean and parse JSON string
                                                cleaned_response = response.strip()
                                                if cleaned_response.startswith("```json"):
                                                    cleaned_response = cleaned_response[7:].lstrip()
                                                elif cleaned_response.startswith("```"):
                                                    cleaned_response = cleaned_response[3:].lstrip()
                                                if cleaned_response.endswith("```"):
                                                    cleaned_response = cleaned_response[:-3].rstrip()
                                                
                                                parsed_response = json.loads(cleaned_response)
                                                if isinstance(parsed_response, dict):
                                                    response = parsed_response
                                                    print(f"      Result {j} parsed from string to dict")
                                            except json.JSONDecodeError:
                                                print(f"      Result {j} string is not valid JSON")
                                        
                                        if isinstance(response, dict):
                                            keys = list(response.keys())
                                            print(f"      Result {j} keys: {keys}")
                                            
                                            # Check for layout review structure
                                            if 'review_type' in response or 'total_slides_reviewed' in response or \
                                               ('passed' in response and 'overall_quality' in response) or \
                                               ('presentation_id' in response and ('issues_summary' in response or 'overall_quality' in response)):
                                                layout_review = response
                                                print("✅ [DEBUG] Found layout_review in tool_result.response!")
                                                break
                                    if layout_review:
                                        break
                        
                        # Also check function_response in content parts
                        if hasattr(event, 'content') and event.content:
                            if hasattr(event.content, 'parts') and event.content.parts:
                                for k, part in enumerate(event.content.parts):
                                    if hasattr(part, 'function_response') and part.function_response:
                                        print(f"      Part {k} has function_response")
                                        if hasattr(part.function_response, 'response'):
                                            response = part.function_response.response
                                            print(f"      Part {k} response type: {type(response).__name__}")
                                            
                                            # Handle string response (often JSON string)
                                            if isinstance(response, str):
                                                try:
                                                    # Try to clean and parse JSON string
                                                    cleaned_response = response.strip()
                                                    if cleaned_response.startswith("```json"):
                                                        cleaned_response = cleaned_response[7:].lstrip()
                                                    elif cleaned_response.startswith("```"):
                                                        cleaned_response = cleaned_response[3:].lstrip()
                                                    if cleaned_response.endswith("```"):
                                                        cleaned_response = cleaned_response[:-3].rstrip()
                                                    
                                                    parsed_response = json.loads(cleaned_response)
                                                    if isinstance(parsed_response, dict):
                                                        response = parsed_response
                                                        print(f"      Part {k} parsed from string to dict")
                                                except json.JSONDecodeError:
                                                    print(f"      Part {k} string is not valid JSON")

                                            if isinstance(response, dict):
                                                keys = list(response.keys())
                                                print(f"      Part {k} response keys: {keys}")
                                                if 'review_type' in response or 'total_slides_reviewed' in response:
                                                    layout_review = response
                                                    print("✅ [DEBUG] Found layout_review in function_response!")
                                                    break
                                    if layout_review:
                                        break
                        
                        if layout_review:
                            break
                
                if layout_review:
                    outputs["layout_review"] = layout_review
                    if save_intermediate:
                        review_file = f"{output_dir}/layout_review.json"
                        save_json_output(layout_review, review_file)
                        print(f"✅ Layout review saved to: {review_file}")
                    obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
                else:
                    obs_logger.finish_agent_execution(AgentStatus.FAILED, "No layout review generated", has_output=False)
                    print(f"⚠️  Layout review not found in events or tool results")
                    # Debug: log what we found
                    logger.warning("   Debug: Checking all events for LayoutCriticAgent...")
                    for i, event in enumerate(events):
                        agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
                        if agent_name == "LayoutCriticAgent":
                            logger.warning(f"   Event {i}: LayoutCriticAgent found")
                            if hasattr(event, 'actions') and event.actions:
                                if hasattr(event.actions, 'tool_results') and event.actions.tool_results:
                                    logger.warning(f"      tool_results: {len(event.actions.tool_results)}")
                                    for j, tr in enumerate(event.actions.tool_results):
                                        if hasattr(tr, 'response'):
                                            logger.warning(f"         tool_result {j} type: {type(tr.response).__name__}")
                                            if isinstance(tr.response, dict):
                                                logger.warning(f"         tool_result {j} keys: {list(tr.response.keys())[:10]}")
        
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
        scenario="academic_teaching",
        duration="1 minute",
        target_audience="students",  # Optional - can be None to let LLM infer from scenario and report content
        custom_instruction="keep the slide as clean as possible, use more point forms, keep the details in speech only",
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
