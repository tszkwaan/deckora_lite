"""
Main script for local development and testing of the presentation generation pipeline.
"""

import os
import asyncio
import json
import datetime
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

from config import PresentationConfig
from agents.orchestrator import create_presentation_pipeline, create_simple_pipeline
from agents.report_understanding import create_report_understanding_agent
from agents.outline_generator import create_outline_generator_agent
from agents.critic import create_outline_critic
from utils.pdf_loader import load_pdf
from utils.helpers import extract_output_from_events, save_json_output, preview_json
from utils.quality_check import check_outline_quality, create_quality_log_entry
from config import OUTLINE_MAX_RETRY_LOOPS


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
            break
        else:
            if attempt < OUTLINE_MAX_RETRY_LOOPS:
                print(f"\n⚠️  Quality check failed. Retrying... ({attempt}/{OUTLINE_MAX_RETRY_LOOPS})")
                for reason in details.get("failure_reasons", []):
                    print(f"   - {reason}")
            else:
                print(f"\n⚠️  WARNING: Maximum retry attempts ({OUTLINE_MAX_RETRY_LOOPS}) reached.")
                print(f"   Proceeding with outline despite quality issues.")
                for reason in details.get("failure_reasons", []):
                    print(f"   - {reason}")
    
    print("=" * 60)
    print("✅ Outline generation complete\n")
    
    # Save outline and review
    if outline:
        outputs["presentation_outline"] = outline
        if save_intermediate:
            output_file = f"{output_dir}/presentation_outline.json"
            save_json_output(outline, output_file)
            print(f"📄 Presentation outline saved to: {output_file}")
            print(f"\nPreview:\n{preview_json(outline)}\n")
    
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
    
    # TODO: Uncomment when other agents are added
    # # Extract design_style_config
    # design_style = extract_output_from_events(events, "design_style_config")
    # if design_style:
    #     outputs["design_style_config"] = design_style
    #     if save_intermediate:
    #         save_json_output(design_style, f"{output_dir}/design_style_config.json")
    # 
    # # Extract slide_deck
    # slide_deck = extract_output_from_events(events, "slide_deck")
    # if slide_deck:
    #     outputs["slide_deck"] = slide_deck
    #     if save_intermediate:
    #         save_json_output(slide_deck, f"{output_dir}/slide_deck.json")
    #         print(f"Preview:\n{preview_json(slide_deck)}\n")
    # 
    # slides_review = extract_output_from_events(events, "critic_review_slides")
    # if slides_review:
    #     outputs["slides_review"] = slides_review
    #     if save_intermediate:
    #         save_json_output(slides_review, f"{output_dir}/slides_review.json")
    # 
    # # Extract presentation_script
    # script = extract_output_from_events(events, "presentation_script")
    # if script:
    #     outputs["presentation_script"] = script
    #     if save_intermediate:
    #         save_json_output(script, f"{output_dir}/presentation_script.json")
    #         print(f"Preview:\n{preview_json(script)}\n")
    # 
    # script_review = extract_output_from_events(events, "critic_review_script")
    # if script_review:
    #     outputs["script_review"] = script_review
    #     if save_intermediate:
    #         save_json_output(script_review, f"{output_dir}/script_review.json")
    
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
        duration="20 minutes",
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

