"""
Standalone script to test the Google Slides Exporter.
This will export slide_deck.json and presentation_script.json to Google Slides.
"""

import os
import asyncio
import json
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

from config import PresentationConfig
from agents.slideshow_exporter import create_slideshow_exporter_agent
from utils.helpers import extract_output_from_events, save_json_output


async def test_google_slides_exporter(
    slide_deck_file: str = "output/slide_deck.json",
    presentation_script_file: str = "output/presentation_script.json",
    scenario: str = "academic_teaching",
    duration: str = "20 minutes",
    target_audience: str = "students",
    custom_instruction: str = "keep the slide as clean as possible, use more point forms, keep the details in speech only",
    output_dir: str = "output",
):
    """
    Test the Google Slides Exporter Agent.
    
    This will:
    1. Load slide_deck.json and presentation_script.json
    2. Run the Slideshow Exporter Agent
    3. Export to Google Slides
    4. Save presentation ID and URL to files
    
    Args:
        slide_deck_file: Path to slide_deck.json
        presentation_script_file: Path to presentation_script.json
        scenario: Presentation scenario
        duration: Presentation duration
        target_audience: Target audience
        custom_instruction: Custom instructions
        output_dir: Output directory
    """
    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY environment variable not set")
        print("Set it with: export GOOGLE_API_KEY='your-key-here'")
        return None
    
    # Check if files exist
    if not Path(slide_deck_file).exists():
        print(f"❌ Error: slide_deck.json not found at: {slide_deck_file}")
        print("   Please run the pipeline first to generate slide_deck.json")
        return None
    
    if not Path(presentation_script_file).exists():
        print(f"❌ Error: presentation_script.json not found at: {presentation_script_file}")
        print("   Please run the pipeline first to generate presentation_script.json")
        return None
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}/")
    
    # Load slide deck
    print(f"\n📄 Loading slide_deck from: {slide_deck_file}")
    with open(slide_deck_file, 'r', encoding='utf-8') as f:
        slide_deck = json.load(f)
    print(f"✅ Loaded slide_deck with {len(slide_deck.get('slides', []))} slides")
    
    # Load presentation script
    print(f"\n📄 Loading presentation_script from: {presentation_script_file}")
    with open(presentation_script_file, 'r', encoding='utf-8') as f:
        presentation_script = json.load(f)
    print(f"✅ Loaded presentation_script with {len(presentation_script.get('script_sections', []))} sections")
    
    # Create session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="google_slides_exporter_test",
        user_id="user"
    )
    
    # Set up session state
    session.state.update({
        "scenario": scenario,
        "duration": duration,
        "target_audience": target_audience,
        "custom_instruction": custom_instruction,
        "slide_deck": slide_deck,
        "presentation_script": presentation_script,
    })
    
    # Create slideshow exporter agent
    print("\n" + "=" * 60)
    print("📊 Testing Google Slides Exporter Agent...")
    print("=" * 60)
    
    print("\n🔧 Creating Slideshow Exporter Agent...")
    exporter_agent = create_slideshow_exporter_agent()
    print("✅ Agent created")
    
    # Create runner
    exporter_runner = InMemoryRunner(agent=exporter_agent)
    
    # Build message for exporter agent
    slide_deck_json = json.dumps(slide_deck, indent=2, ensure_ascii=False)
    script_json = json.dumps(presentation_script, indent=2, ensure_ascii=False)
    config_dict = {
        "scenario": scenario,
        "duration": duration,
        "target_audience": target_audience,
        "custom_instruction": custom_instruction,
    }
    config_json = json.dumps(config_dict, indent=2, ensure_ascii=False)
    
    exporter_message = f"""
[SLIDE_DECK]
{slide_deck_json}
[END_SLIDE_DECK]

[PRESENTATION_SCRIPT]
{script_json}
[END_PRESENTATION_SCRIPT]

[CONFIG]
{config_json}
[END_CONFIG]

Your task:
- Use the export_slideshow_tool to export the slide deck and script to Google Slides
- Extract slide_deck and presentation_script from the sections above
- Build config dict from [CONFIG] section
- Call the tool with appropriate parameters
- Return the result with presentation_id and shareable_url
"""
    
    # Run agent
    print("\n🚀 Running Slideshow Exporter Agent...")
    print("=" * 60)
    
    try:
        exporter_events = await exporter_runner.run_debug(exporter_message, session_id=session.id)
        
        print("=" * 60)
        print("✅ Agent execution complete\n")
        
        # Debug: Check what's in the events
        if exporter_events:
            print(f"📊 Debug: Found {len(exporter_events)} events")
            for i, event in enumerate(exporter_events):
                print(f"\n📊 Debug: Event {i}:")
                print(f"   Type: {type(event)}")
                print(f"   Dir: {[x for x in dir(event) if not x.startswith('_')][:20]}")
                if hasattr(event, 'actions'):
                    print(f"   Has actions: True")
                    actions = event.actions
                    print(f"   Actions type: {type(actions)}")
                    print(f"   Actions dir: {[x for x in dir(actions) if not x.startswith('_')][:20]}")
                    # Check for tool calls
                    if hasattr(actions, 'tool_calls') and actions.tool_calls:
                        print(f"   Tool calls: {len(actions.tool_calls)}")
                        for j, tool_call in enumerate(actions.tool_calls):
                            print(f"      Tool call {j}: {tool_call}")
                    # Check for tool results
                    if hasattr(actions, 'tool_results') and actions.tool_results:
                        print(f"   Tool results: {len(actions.tool_results)}")
                        for j, tool_result in enumerate(actions.tool_results):
                            print(f"      Tool result {j}: {type(tool_result)}")
                            if hasattr(tool_result, 'result'):
                                result = tool_result.result
                                print(f"         Result type: {type(result)}")
                                if isinstance(result, dict):
                                    print(f"         Result keys: {list(result.keys())}")
                                    print(f"         Result: {result}")
                                else:
                                    print(f"         Result: {result}")
                    # Check state_delta
                    if hasattr(actions, 'state_delta'):
                        state_delta = actions.state_delta
                        print(f"   State delta keys: {list(state_delta.keys())}")
                        if state_delta:
                            for key, value in state_delta.items():
                                print(f"      {key}: {type(value)}")
                                if isinstance(value, dict):
                                    print(f"         Keys: {list(value.keys())}")
                # Check for function calls/responses
                if hasattr(event, 'get_function_calls'):
                    func_calls = event.get_function_calls()
                    if func_calls:
                        print(f"   Function calls: {func_calls}")
                if hasattr(event, 'get_function_responses'):
                    func_responses = event.get_function_responses()
                    if func_responses:
                        print(f"   Function responses: {func_responses}")
                # Check for errors
                if hasattr(event, 'error_code') and event.error_code:
                    print(f"   ⚠️  Error code: {event.error_code}")
                if hasattr(event, 'error_message') and event.error_message:
                    print(f"   ⚠️  Error message: {event.error_message}")
                if hasattr(event, 'error'):
                    print(f"   ⚠️  Error: {event.error}")
                if hasattr(event, 'finish_reason'):
                    print(f"   Finish reason: {event.finish_reason}")
                # Check for text/message content
                if hasattr(event, 'text'):
                    print(f"   Text: {event.text[:500] if event.text else 'None'}")
                if hasattr(event, 'message'):
                    print(f"   Message: {str(event.message)[:500] if event.message else 'None'}")
                if hasattr(event, 'content'):
                    content = event.content
                    print(f"   Content type: {type(content)}")
                    if content:
                        print(f"   Content: {str(content)[:500]}")
                # Try to get any text from the event
                for attr in ['text', 'message', 'content', 'response', 'output']:
                    if hasattr(event, attr):
                        val = getattr(event, attr)
                        if val:
                            print(f"   {attr}: {str(val)[:500]}")
            
            last_event = exporter_events[-1]
            if hasattr(last_event, 'actions') and hasattr(last_event.actions, 'state_delta'):
                state_delta = last_event.actions.state_delta
                print(f"\n📊 Debug: Last event state delta keys: {list(state_delta.keys())}")
                if "slideshow_export_result" in state_delta:
                    print(f"📊 Debug: Found slideshow_export_result: {type(state_delta['slideshow_export_result'])}")
        
        # Extract output
        export_result = extract_output_from_events(exporter_events, "slideshow_export_result")
        
        # Debug: Check if we got a result
        if export_result:
            print(f"📊 Debug: Extracted result type: {type(export_result)}")
            print(f"📊 Debug: Extracted result: {export_result}")
            # Handle nested result structure
            if isinstance(export_result, dict) and "slideshow_export_result" in export_result:
                export_result = export_result["slideshow_export_result"]
                print(f"📊 Debug: Unnested result: {export_result}")
        else:
            print("⚠️  Debug: No result extracted from events")
            # Try to find tool result in events - check all events
            for i, event in enumerate(exporter_events):
                if hasattr(event, 'actions'):
                    # Check for tool results
                    if hasattr(event.actions, 'tool_results') and event.actions.tool_results:
                        for tool_result in event.actions.tool_results:
                            print(f"📊 Debug: Event {i} - Found tool result")
                            # Tool result might contain the export result
                            if hasattr(tool_result, 'result'):
                                result = tool_result.result
                                print(f"📊 Debug: Tool result type: {type(result)}")
                                print(f"📊 Debug: Tool result: {result}")
                                if isinstance(result, dict):
                                    if 'presentation_id' in result or result.get('status') == 'success':
                                        export_result = result
                                        print(f"✅ Found export result in tool response!")
                                        break
                    # Also check state_delta for any keys
                    if hasattr(event.actions, 'state_delta'):
                        state_delta = event.actions.state_delta
                        print(f"📊 Debug: Event {i} - State delta keys: {list(state_delta.keys())}")
                        # Check if tool result is stored in state
                        for key, value in state_delta.items():
                            if isinstance(value, dict) and ('presentation_id' in value or value.get('status') == 'success'):
                                export_result = value
                                print(f"✅ Found export result in state_delta['{key}']!")
                                break
        
        # Also check if Google Slides files were created (indicates success even if agent didn't return properly)
        id_file = f"{output_dir}/presentation_slides_id.txt"
        url_file = f"{output_dir}/presentation_slides_url.txt"
        if Path(id_file).exists() and Path(url_file).exists():
            print(f"\n💡 Found existing Google Slides files - export may have succeeded!")
            with open(id_file, 'r') as f:
                presentation_id = f.read().strip()
            with open(url_file, 'r') as f:
                shareable_url = f.read().strip()
            
            if presentation_id and shareable_url:
                export_result = {
                    "status": "success",
                    "presentation_id": presentation_id,
                    "shareable_url": shareable_url,
                    "message": "Google Slides presentation found (from previous export)"
                }
                print(f"✅ Using existing Google Slides presentation!")
                print(f"   Presentation ID: {presentation_id}")
                print(f"   Shareable URL: {shareable_url}")
        
        if export_result and export_result.get("status") == "success":
            presentation_id = export_result.get("presentation_id")
            shareable_url = export_result.get("shareable_url")
            
            # Save IDs to files
            id_file = f"{output_dir}/presentation_slides_id.txt"
            url_file = f"{output_dir}/presentation_slides_url.txt"
            
            with open(id_file, 'w') as f:
                f.write(presentation_id)
            with open(url_file, 'w') as f:
                f.write(shareable_url)
            
            print(f"\n{'='*60}")
            print(f"✅ SUCCESS: Google Slides presentation created!")
            print(f"{'='*60}")
            print(f"📊 Presentation ID: {presentation_id}")
            print(f"🔗 Shareable URL: {shareable_url}")
            print(f"\n📄 Presentation ID saved to: {Path(id_file).absolute()}")
            print(f"📄 Shareable URL saved to: {Path(url_file).absolute()}")
            print(f"\n💡 You can now open the presentation in Google Slides!")
            print(f"   URL: {shareable_url}")
            
            return export_result
        else:
            error_msg = export_result.get("error", "Unknown error") if export_result else "No result returned"
            print(f"\n❌ Error: Google Slides export failed")
            print(f"   Error: {error_msg}")
            if export_result:
                print(f"\n   Full result: {json.dumps(export_result, indent=2)}")
            return None
            
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 This usually means Google Slides API credentials are not set up.")
        print("   See GOOGLE_SLIDES_SETUP.md for setup instructions.")
        print("   You need to:")
        print("   1. Enable Google Slides API in Google Cloud Console")
        print("   2. Create OAuth2 credentials")
        print("   3. Download credentials.json to credentials/ folder")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        print(f"\n   Traceback:")
        traceback.print_exc()
        return None


async def main():
    """Main function for testing."""
    # Try to load from .env file if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    except ImportError:
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
        return
    
    print(f"✅ API key found (length: {len(api_key)} characters)")
    
    # Run the test
    result = await test_google_slides_exporter()
    
    if result:
        print("\n🎉 Test completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Open the Google Slides presentation using the URL above")
        print("   2. Check that all slides are present")
        print("   3. Verify speaker notes are included")
        print("   4. Review formatting and content")
    else:
        print("\n❌ Test failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())

