"""
Standalone script to test only the Report Understanding Agent.
This will generate report_knowledge.json in the output folder.
"""

import os
import asyncio
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

from config import PresentationConfig
from agents.report_understanding import create_report_understanding_agent
from utils.pdf_loader import load_pdf
from utils.helpers import extract_output_from_events, save_json_output, preview_json


async def test_report_understanding_agent(
    report_url: str = "https://arxiv.org/pdf/2511.08597",
    scenario: str = "academic_teaching",
    duration: str = "20 minutes",
    target_audience: str = "students",
    custom_instruction: str = "keep the slide as clean as possible, use more point forms, keep the details in speech only",
    output_dir: str = "output",
):
    """
    Test the Report Understanding Agent standalone.
    
    This will:
    1. Load the PDF from the URL
    2. Run the Report Understanding Agent
    3. Save report_knowledge.json to the output folder
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
    
    # Load PDF
    print(f"\n📄 Loading PDF from URL: {report_url}")
    report_content = load_pdf(report_url=report_url)
    print(f"✅ Loaded {len(report_content)} characters")
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="presentation_agent_test",
        user_id="user"
    )
    
    # Set up session state
    session.state.update({
        "scenario": scenario,
        "duration": duration,
        "target_audience": target_audience,
        "custom_instruction": custom_instruction,
        "report_url": report_url,
        "report_content": report_content,
    })
    
    # Create agent
    print("\n🔧 Creating Report Understanding Agent...")
    agent = create_report_understanding_agent()
    print("✅ Agent created")
    
    # Create runner
    runner = InMemoryRunner(agent=agent)
    
    # Build initial message
    initial_message = f"""
[SCENARIO]
{scenario}

[DURATION]
{duration}

[TARGET_AUDIENCE]
{target_audience}

[CUSTOM_INSTRUCTION]
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
    print("\n🚀 Running Report Understanding Agent...")
    print("=" * 60)
    
    events = await runner.run_debug(initial_message)
    
    print("=" * 60)
    print("✅ Agent execution complete\n")
    
    # Extract output
    report_knowledge = extract_output_from_events(events, "report_knowledge")
    
    if report_knowledge:
        # Save to file
        output_file = f"{output_dir}/report_knowledge.json"
        save_json_output(report_knowledge, output_file)
        
        print(f"\n{'='*60}")
        print(f"✅ SUCCESS: report_knowledge.json generated!")
        print(f"{'='*60}")
        print(f"📄 File location: {Path(output_file).absolute()}")
        print(f"📊 File size: {Path(output_file).stat().st_size} bytes")
        print(f"\nPreview (first 2000 characters):")
        print("-" * 60)
        print(preview_json(report_knowledge, max_chars=2000))
        print("-" * 60)
        
        return report_knowledge
    else:
        print("❌ Error: No report_knowledge found in agent output")
        print("Check the events to see what happened:")
        if events:
            print(f"Total events: {len(events)}")
            if len(events) > 0:
                last_event = events[-1]
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
    
    # Run the test
    result = await test_report_understanding_agent()
    
    if result:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n❌ Test failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())

