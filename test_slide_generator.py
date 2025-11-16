"""
Standalone script to test only the Slide Generator Agent.
This will generate slide_deck.json in the output folder.
"""

import os
import asyncio
import json
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

from config import PresentationConfig
from agents.slide_and_script_generator import create_slide_and_script_generator_agent
from agents.outline_generator import create_outline_generator_agent
from agents.report_understanding import create_report_understanding_agent
from utils.pdf_loader import load_pdf
from utils.helpers import extract_output_from_events, save_json_output, preview_json


async def test_slide_generator_agent(
    report_knowledge_file: str = None,
    presentation_outline_file: str = None,
    report_url: str = "https://arxiv.org/pdf/2511.08597",
    scenario: str = "academic_teaching",
    duration: str = "20 minutes",
    target_audience: str = "students",
    custom_instruction: str = "keep the slide as clean as possible, use more point forms, keep the details in speech only",
    output_dir: str = "output",
    generate_missing: bool = True,
):
    """
    Test the Slide Generator Agent standalone.
    
    This will:
    1. Load report_knowledge (from file or generate if needed)
    2. Load presentation_outline (from file or generate if needed)
    3. Run the Slide Generator Agent
    4. Save slide_deck.json to the output folder
    
    Args:
        report_knowledge_file: Path to existing report_knowledge.json (optional)
        presentation_outline_file: Path to existing presentation_outline.json (optional)
        report_url: URL to PDF if generating missing files
        scenario: Presentation scenario
        duration: Presentation duration
        target_audience: Target audience
        custom_instruction: Custom instructions
        output_dir: Output directory
        generate_missing: If True, generate missing files instead of failing
    """
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY environment variable not set")
        print("Set it with: export GOOGLE_API_KEY='your-key-here'")
        return None
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}/")
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="slide_generator_test",
        user_id="user"
    )
    
    # Load or generate report_knowledge
    report_knowledge = None
    if report_knowledge_file and Path(report_knowledge_file).exists():
        print(f"\n📄 Loading report_knowledge from: {report_knowledge_file}")
        with open(report_knowledge_file, 'r', encoding='utf-8') as f:
            report_knowledge = json.load(f)
        print("✅ Loaded report_knowledge")
    elif generate_missing:
        print("\n📄 Generating report_knowledge...")
        print("=" * 60)
        
        # Load PDF
        print(f"📄 Loading PDF from URL: {report_url}")
        report_content = load_pdf(report_url=report_url)
        print(f"✅ Loaded {len(report_content)} characters")
        
        # Create report understanding agent
        report_agent = create_report_understanding_agent()
        report_runner = InMemoryRunner(agent=report_agent)
        
        # Set up session state
        session.state.update({
            "scenario": scenario,
            "duration": duration,
            "target_audience": target_audience,
            "custom_instruction": custom_instruction,
            "report_url": report_url,
            "report_content": report_content,
        })
        
        # Build message
        target_audience_section = f"[TARGET_AUDIENCE]\n{target_audience}\n" if target_audience else "[TARGET_AUDIENCE]\nN/A\n"
        report_message = f"""
[SCENARIO]
{scenario}

[DURATION]
{duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{custom_instruction}

[REPORT_URL]
{report_url}

[REPORT_CONTENT]
{report_content}
[END_REPORT_CONTENT]

Your task:
- Use ONLY the above information.
- Produce the required `report_knowledge` JSON.
- Do NOT ask any questions.
"""
        
        # Run agent
        print("🚀 Running Report Understanding Agent...")
        report_events = await report_runner.run_debug(report_message, session_id=session.id)
        report_knowledge = extract_output_from_events(report_events, "report_knowledge")
        
        if report_knowledge:
            # Save it
            report_file = f"{output_dir}/report_knowledge.json"
            save_json_output(report_knowledge, report_file)
            print(f"✅ Generated and saved report_knowledge to: {report_file}")
        else:
            print("❌ Error: Failed to generate report_knowledge")
            return None
    else:
        print("❌ Error: report_knowledge not found and generate_missing=False")
        return None
    
    # Load or generate presentation_outline
    presentation_outline = None
    if presentation_outline_file and Path(presentation_outline_file).exists():
        print(f"\n📄 Loading presentation_outline from: {presentation_outline_file}")
        with open(presentation_outline_file, 'r', encoding='utf-8') as f:
            presentation_outline = json.load(f)
        print("✅ Loaded presentation_outline")
    elif generate_missing:
        print("\n📄 Generating presentation_outline...")
        print("=" * 60)
        
        # Create outline generator agent
        outline_agent = create_outline_generator_agent()
        outline_runner = InMemoryRunner(agent=outline_agent)
        
        # Update session state
        session.state["report_knowledge"] = report_knowledge
        
        # Build message
        report_knowledge_json = json.dumps(report_knowledge, indent=2, ensure_ascii=False)
        target_audience_section = f"[TARGET_AUDIENCE]\n{target_audience or 'N/A'}\n" if target_audience else "[TARGET_AUDIENCE]\nN/A\n"
        
        outline_message = f"""
[REPORT_KNOWLEDGE]
{report_knowledge_json}
[END_REPORT_KNOWLEDGE]

[SCENARIO]
{scenario}

[DURATION]
{duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{custom_instruction}

Your task:
- Generate a presentation outline based ONLY on the [REPORT_KNOWLEDGE] provided above.
- Use the scenario, duration, and custom_instruction to guide structure and focus.
- Do NOT invent any facts, numbers, or technical details not in the report_knowledge.
- All content must be traceable to report_knowledge sections.
- Output the outline as JSON in the required format.
- Do NOT ask any questions - all data is provided above.
"""
        
        # Run agent
        print("🚀 Running Outline Generator Agent...")
        outline_events = await outline_runner.run_debug(outline_message, session_id=session.id)
        presentation_outline = extract_output_from_events(outline_events, "presentation_outline")
        
        if presentation_outline:
            # Save it
            outline_file = f"{output_dir}/presentation_outline.json"
            save_json_output(presentation_outline, outline_file)
            print(f"✅ Generated and saved presentation_outline to: {outline_file}")
        else:
            print("❌ Error: Failed to generate presentation_outline")
            return None
    else:
        print("❌ Error: presentation_outline not found and generate_missing=False")
        return None
    
    # Now run slide generator
    print("\n" + "=" * 60)
    print("🎨 Testing Slide Generator Agent...")
    print("=" * 60)
    
    # Update session state
    session.state.update({
        "scenario": scenario,
        "duration": duration,
        "target_audience": target_audience,
        "custom_instruction": custom_instruction,
        "report_knowledge": report_knowledge,
        "presentation_outline": presentation_outline,
    })
    
    # Create combined slide and script generator agent
    print("\n🔧 Creating Slide and Script Generator Agent...")
    combined_agent = create_slide_and_script_generator_agent()
    print("✅ Agent created")
    
    # Create runner
    combined_runner = InMemoryRunner(agent=combined_agent)
    
    # Build message
    outline_json = json.dumps(presentation_outline, indent=2, ensure_ascii=False)
    report_knowledge_json = json.dumps(report_knowledge, indent=2, ensure_ascii=False)
    target_audience_section = f"[TARGET_AUDIENCE]\n{target_audience or 'N/A'}\n" if target_audience else "[TARGET_AUDIENCE]\nN/A\n"
    
    combined_message = f"""
[PRESENTATION_OUTLINE]
{outline_json}
[END_PRESENTATION_OUTLINE]

[REPORT_KNOWLEDGE]
{report_knowledge_json}
[END_REPORT_KNOWLEDGE]

[SCENARIO]
{scenario}

[DURATION]
{duration}

{target_audience_section}[CUSTOM_INSTRUCTION]
{custom_instruction}

Your task:
- Generate BOTH slide deck AND presentation script in a single response.
- Generate detailed slide content based ONLY on the [PRESENTATION_OUTLINE] and [REPORT_KNOWLEDGE] provided above.
- Generate a detailed presentation script that expands on the slide content with detailed explanations.
- Use the scenario, duration, and custom_instruction to guide both slide and script content.
- Do NOT invent any facts, numbers, or technical details not in the report_knowledge.
- All content must be traceable to report_knowledge sections.
- Output BOTH slide_deck and presentation_script as JSON in the required format.
- Do NOT ask any questions - all data is provided above.
"""
    
    # Run agent
    print("\n🚀 Running Slide and Script Generator Agent...")
    print("=" * 60)
    
    combined_events = await combined_runner.run_debug(combined_message, session_id=session.id)
    
    print("=" * 60)
    print("✅ Agent execution complete\n")
    
    # Extract output
    combined_output = extract_output_from_events(combined_events, "slide_and_script")
    
    # Extract slide_deck and script from combined output
    if combined_output and isinstance(combined_output, dict):
        slide_deck = combined_output.get("slide_deck")
        script = combined_output.get("presentation_script")
    else:
        slide_deck = None
        script = None
    
    if slide_deck:
        # Save to file
        output_file = f"{output_dir}/slide_deck.json"
        save_json_output(slide_deck, output_file)
        
        print(f"\n{'='*60}")
        print(f"✅ SUCCESS: slide_deck.json generated!")
        print(f"{'='*60}")
        print(f"📄 File location: {Path(output_file).absolute()}")
        print(f"📊 File size: {Path(output_file).stat().st_size} bytes")
        print(f"📊 Total slides: {len(slide_deck.get('slides', []))}")
        print(f"\nPreview (first 2000 characters):")
        print("-" * 60)
        print(preview_json(slide_deck, max_chars=2000))
        print("-" * 60)
        
        return slide_deck
    else:
        print("❌ Error: No slide_deck found in agent output")
        print("Check the events to see what happened:")
        if slide_events:
            print(f"Total events: {len(slide_events)}")
            if len(slide_events) > 0:
                last_event = slide_events[-1]
                print(f"Last event actions: {last_event.actions}")
        return None


async def main():
    """Main function for testing."""
    # Try to load from .env file if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    # Check if existing files are available
    output_dir = "output"
    report_knowledge_file = f"{output_dir}/report_knowledge.json"
    presentation_outline_file = f"{output_dir}/presentation_outline.json"
    
    # Use existing files if available, otherwise generate them
    use_existing = Path(report_knowledge_file).exists() and Path(presentation_outline_file).exists()
    
    if use_existing:
        print("📁 Found existing report_knowledge.json and presentation_outline.json")
        print("   Using existing files. Set generate_missing=False to skip generation.")
    else:
        print("📁 Missing some files, will generate them automatically")
    
    # Run the test
    result = await test_slide_generator_agent(
        report_knowledge_file=report_knowledge_file if use_existing else None,
        presentation_outline_file=presentation_outline_file if use_existing else None,
        generate_missing=True,
    )
    
    if result:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n❌ Test failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())

