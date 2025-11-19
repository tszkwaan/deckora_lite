"""
Simple test script to verify the pipeline works locally.
"""
import os
import asyncio
import logging
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from presentation_agent.agent import root_agent
from presentation_agent.agents.utils.helpers import extract_output_from_events

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def test_pipeline():
    """Test the presentation pipeline locally."""
    print("🚀 Starting pipeline test...")
    
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
        return
    
    print(f"✅ API key found: {os.getenv('GOOGLE_API_KEY')[:10]}...")
    
    # Build initial message (similar to server.py)
    initial_message = """
[SCENARIO]
academic_teaching

[DURATION]
1 minute

[TARGET_AUDIENCE]
students

[CUSTOM_INSTRUCTION]
keep slides clean

[REPORT_URL]
https://arxiv.org/pdf/2511.08597

[REPORT_CONTENT]
N/A

Your task:
- Use ONLY the above information.
- Generate a complete presentation following the pipeline.
- Do NOT ask any questions.
- Do NOT invent information not in the report_content.
"""
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="presentation_agent",
        user_id="test_user"
    )
    
    # Set up session state
    session.state.update({
        "scenario": "academic_teaching",
        "duration": "1 minute",
        "target_audience": "students",
        "custom_instruction": "keep slides clean",
        "report_url": "https://arxiv.org/pdf/2511.08597",
    })
    
    print("📋 Running pipeline...")
    print(f"   Root agent: {root_agent.name}")
    print(f"   Root agent type: {type(root_agent)}")
    
    # Create runner and execute
    runner = InMemoryRunner(agent=root_agent)
    
    try:
        events = await runner.run_debug(initial_message, session_id=session.id)
        
        print("\n✅ Pipeline completed!")
        print(f"\n📊 Total events: {len(events)}")
        print(f"📊 Session state keys: {list(session.state.keys())}")
        
        # Debug: Inspect all events to see which agents ran
        print("\n🔍 Inspecting all events to see which agents ran...")
        agent_names_seen = set()
        for i, event in enumerate(events):
            if hasattr(event, 'agent_name') and event.agent_name:
                agent_names_seen.add(event.agent_name)
            if hasattr(event, 'actions') and event.actions:
                if hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                    print(f"   Event {i}: state_delta keys: {list(event.actions.state_delta.keys())}")
        print(f"\n   Agents that ran: {sorted(agent_names_seen)}")
        
        # Extract outputs from events (ADK stores outputs in events, not automatically in session.state)
        print("\n🔍 Extracting outputs from events...")
        report_knowledge = extract_output_from_events(events, "report_knowledge")
        presentation_outline = extract_output_from_events(events, "presentation_outline")
        slide_and_script = extract_output_from_events(events, "slide_and_script")
        slides_export_result = extract_output_from_events(events, "slides_export_result")
        
        # Print extraction results
        if report_knowledge:
            print(f"✅ Extracted report_knowledge from events")
            session.state["report_knowledge"] = report_knowledge
        else:
            print(f"⚠️  No report_knowledge found in events")
            
        if presentation_outline:
            print(f"✅ Extracted presentation_outline from events")
            session.state["presentation_outline"] = presentation_outline
        else:
            print(f"⚠️  No presentation_outline found in events")
            
        if slide_and_script:
            print(f"✅ Extracted slide_and_script from events")
            session.state["slide_and_script"] = slide_and_script
        else:
            print(f"⚠️  No slide_and_script found in events")
            
        if slides_export_result:
            print(f"✅ Extracted slides_export_result from events")
            session.state["slides_export_result"] = slides_export_result
        else:
            print(f"⚠️  No slides_export_result found in events")
        
        # Print all session state values for debugging
        print(f"\n🔍 Full session.state contents after extraction:")
        for key, value in session.state.items():
            if isinstance(value, dict):
                print(f"   {key}: {type(value).__name__} with keys: {list(value.keys())[:5]}...")
            elif isinstance(value, str) and len(value) > 100:
                print(f"   {key}: {type(value).__name__} (length: {len(value)}, first 100 chars: {value[:100]}...)")
            else:
                print(f"   {key}: {value}")
        
        # Check for key outputs
        if slides_export_result:
            result = slides_export_result
            print(f"\n🎯 Slides Export Result:")
            if isinstance(result, dict):
                print(f"   Status: {result.get('status')}")
                print(f"   Presentation ID: {result.get('presentation_id')}")
                print(f"   Shareable URL: {result.get('shareable_url')}")
            else:
                print(f"   Result: {result}")
        else:
            print("\n⚠️  No slides_export_result found in session.state")
        
        if slide_and_script:
            slide_script = slide_and_script
            print(f"\n✅ slide_and_script found in session.state")
            if isinstance(slide_script, dict):
                print(f"   Type: dict with keys: {list(slide_script.keys())}")
            elif isinstance(slide_script, str):
                print(f"   Type: string (length: {len(slide_script)})")
                # Try to parse as JSON
                try:
                    import json
                    parsed = json.loads(slide_script)
                    print(f"   ✅ Successfully parsed as JSON")
                except:
                    print(f"   ⚠️  Could not parse as JSON")
        else:
            print(f"\n⚠️  No slide_and_script found in session.state")
        
        # Check for other expected outputs
        if session.state.get("report_knowledge"):
            print(f"\n✅ report_knowledge found in session.state")
        else:
            print(f"\n⚠️  No report_knowledge found in session.state")
            
        if session.state.get("presentation_outline"):
            print(f"\n✅ presentation_outline found in session.state")
        else:
            print(f"\n⚠️  No presentation_outline found in session.state")
            
    except Exception as e:
        print(f"\n❌ Error during pipeline execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipeline())

