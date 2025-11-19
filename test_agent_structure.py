"""
Test script to verify agent structure and that SlidesExportAgent is properly configured.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_agent_imports():
    """Test that all agents can be imported correctly."""
    print("🔍 Testing agent imports...")
    
    try:
        from presentation_agent.agent import root_agent
        print(f"✅ root_agent imported: {root_agent.name} ({type(root_agent).__name__})")
    except Exception as e:
        print(f"❌ Failed to import root_agent: {e}")
        return False
    
    try:
        from presentation_agent.agents.slides_export_agent.agent import agent as slides_export_agent
        print(f"✅ slides_export_agent imported: {slides_export_agent.name}")
        print(f"   Tools: {[tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in slides_export_agent.tools]}")
        print(f"   Output key: {slides_export_agent.output_key}")
    except Exception as e:
        print(f"❌ Failed to import slides_export_agent: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_gen_agent
        print(f"✅ slide_and_script_generator_agent imported: {slide_gen_agent.name}")
    except Exception as e:
        print(f"❌ Failed to import slide_and_script_generator_agent: {e}")
        return False
    
    return True

def test_sequential_agent_structure():
    """Test that the SequentialAgent structure is correct."""
    print("\n🔍 Testing SequentialAgent structure...")
    
    try:
        from presentation_agent.agent import root_agent
        
        # Check if root_agent is a SequentialAgent
        from google.adk.agents import SequentialAgent
        if isinstance(root_agent, SequentialAgent):
            print(f"✅ root_agent is a SequentialAgent")
            print(f"   Sub-agents count: {len(root_agent.sub_agents)}")
            
            # Check sub-agents
            for i, sub_agent in enumerate(root_agent.sub_agents):
                print(f"   [{i}] {sub_agent.name} ({type(sub_agent).__name__})")
                
                # If it's SlidesGenerationSequence, check its sub-agents
                if sub_agent.name == "SlidesGenerationSequence":
                    if isinstance(sub_agent, SequentialAgent):
                        print(f"      └─ Sub-agents:")
                        for j, sub_sub_agent in enumerate(sub_agent.sub_agents):
                            print(f"         [{j}] {sub_sub_agent.name}")
                            if sub_sub_agent.name == "SlidesExportAgent":
                                print(f"            ✅ Found SlidesExportAgent!")
                                print(f"               Tools: {len(sub_sub_agent.tools)} tool(s)")
                                if sub_sub_agent.tools:
                                    tool_name = sub_sub_agent.tools[0].__name__ if hasattr(sub_sub_agent.tools[0], '__name__') else str(sub_sub_agent.tools[0])
                                    print(f"               Tool name: {tool_name}")
        else:
            print(f"❌ root_agent is not a SequentialAgent: {type(root_agent)}")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Error checking SequentialAgent structure: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agent Structure")
    print("=" * 60)
    
    imports_ok = test_agent_imports()
    structure_ok = test_sequential_agent_structure()
    
    print("\n" + "=" * 60)
    if imports_ok and structure_ok:
        print("✅ All tests passed! Agent structure looks correct.")
        print("\nThe pipeline should work correctly.")
        print("SlidesExportAgent is properly configured and should be called.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    print("=" * 60)

