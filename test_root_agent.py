"""
Simple test script to test root_agent with detailed logging.
This uses the updated presentation_agent structure with LoopAgent.
"""
import asyncio
import os
import sys
import logging
from pathlib import Path

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_root_agent.log')
    ]
)

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Try to load from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

# Check for API key
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ GOOGLE_API_KEY not set. Please set it:")
    print("   export GOOGLE_API_KEY='your-key-here'")
    print("   Or create a .env file with: GOOGLE_API_KEY=your-key-here")
    sys.exit(1)

print(f"✅ API key found: {os.getenv('GOOGLE_API_KEY')[:10]}...")

from presentation_agent.agent import root_agent
from config import PresentationConfig
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from presentation_agent.agents.utils.helpers import extract_output_from_events

async def test_root_agent():
    """Test the root_agent pipeline with detailed logging."""
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("🚀 Starting root_agent test")
    logger.info("=" * 80)
    
    # Create config
    config = PresentationConfig(
        scenario="academic_teaching",
        duration="1 minute",
        target_audience="students",
        custom_instruction="keep slides clean",
        report_url="https://arxiv.org/pdf/2511.08597",
        report_content=None,
        style_images=[]
    )
    
    # Build initial message
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
N/A

Your task:
- Use ONLY the above information.
- Generate a complete presentation following the pipeline.
- Do NOT ask any questions.
- Do NOT invent information not in the report_content.
"""
    
    logger.info(f"📋 Root agent: {root_agent.name}")
    logger.info(f"📋 Root agent type: {type(root_agent).__name__}")
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="presentation_agent",
        user_id="test_user"
    )
    
    # Set up session state
    session.state.update(config.to_dict())
    
    # Create runner and execute
    runner = InMemoryRunner(agent=root_agent)
    
    try:
        logger.info("🔄 Running root_agent pipeline...")
        events = await runner.run_debug(initial_message, session_id=session.id)
        
        logger.info("=" * 80)
        logger.info("✅ Pipeline completed!")
        logger.info("=" * 80)
        logger.info(f"📊 Total events: {len(events)}")
        logger.info(f"📊 Session state keys: {list(session.state.keys())}")
        
        # Extract outputs
        logger.info("\n🔍 Extracting outputs from events...")
        report_knowledge = extract_output_from_events(events, "report_knowledge")
        presentation_outline = extract_output_from_events(events, "presentation_outline")
        slide_and_script = extract_output_from_events(events, "slide_and_script")
        slides_export_result = extract_output_from_events(events, "slides_export_result")
        
        # Print results
        logger.info("\n" + "=" * 80)
        logger.info("📊 EXTRACTION RESULTS:")
        logger.info("=" * 80)
        logger.info(f"✅ report_knowledge: {'Found' if report_knowledge else 'NOT FOUND'}")
        logger.info(f"✅ presentation_outline: {'Found' if presentation_outline else 'NOT FOUND'}")
        logger.info(f"✅ slide_and_script: {'Found' if slide_and_script else 'NOT FOUND'}")
        logger.info(f"✅ slides_export_result: {'Found' if slides_export_result else 'NOT FOUND'}")
        
        if slides_export_result:
            logger.info("\n🎯 Slides Export Result:")
            if isinstance(slides_export_result, dict):
                logger.info(f"   Status: {slides_export_result.get('status')}")
                logger.info(f"   Presentation ID: {slides_export_result.get('presentation_id')}")
                logger.info(f"   Shareable URL: {slides_export_result.get('shareable_url')}")
                print(f"\n✅✅✅ SUCCESS! Google Slides URL: {slides_export_result.get('shareable_url')}")
            else:
                logger.info(f"   Result type: {type(slides_export_result).__name__}")
                logger.info(f"   Result: {slides_export_result}")
        else:
            logger.warning("\n⚠️⚠️⚠️ WARNING: slides_export_result NOT FOUND!")
            logger.warning("   This means SlidesExportAgent did not run or did not produce output.")
            logger.warning("   Check the logs above for detailed event inspection.")
            
    except Exception as e:
        logger.error(f"\n❌ Error during pipeline execution: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    asyncio.run(test_root_agent())

