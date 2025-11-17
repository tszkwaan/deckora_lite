"""
Orchestrator Agent and Pipeline Setup.
Coordinates the entire presentation generation pipeline.
"""

from google.adk.agents import SequentialAgent, LoopAgent
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

from .report_understanding import create_report_understanding_agent
from .outline_generator import create_outline_generator_agent
from .critic import create_outline_critic
# TODO: Uncomment when ready to add these agents
# from .slide_and_script_generator import create_slide_and_script_generator_agent
# from .critic import create_slides_critic, create_script_critic


def create_presentation_pipeline(include_critics: bool = True):
    """
    Create the complete presentation generation pipeline.
    
    Args:
        include_critics: Whether to include critic agents in the pipeline
        
    Returns:
        SequentialAgent representing the full pipeline
    """
    # Core pipeline agents
    agents = [
        create_report_understanding_agent(),
        create_outline_generator_agent(),
    ]
    
    # Add critics if enabled - review outline and script draft before generating slides
    if include_critics:
        agents.append(create_outline_critic())
        # Optionally add a loop agent to refine outline based on critic feedback
        # For now, we'll keep it simple and sequential
    
    # Continue with slide and script generation
    # agents.append(create_slide_and_script_generator_agent())
    
    # if include_critics:
    #     agents.append(create_slides_critic())
    
    # if include_critics:
    #     agents.append(create_script_critic())
    
    # Create the root orchestrator
    root_agent = SequentialAgent(
        name="PresentationPipeline",
        description=(
            "Presentation generation pipeline. "
            "Currently executes: report understanding, outline generation, outline critic. "
            "Additional agents will be added incrementally."
        ),
        sub_agents=agents,
    )
    
    return root_agent


def create_simple_pipeline(without_style: bool = False, without_critics: bool = False):
    """
    Create a simplified pipeline for testing or specific use cases.
    
    Currently only includes report understanding agent.
    
    Args:
        without_style: Skip style extraction agent (not used currently)
        without_critics: Skip all critic agents (not used currently)
        
    Returns:
        SequentialAgent representing the pipeline
    """
    agents = [
        create_report_understanding_agent(),
    ]
    
    # TODO: Uncomment when ready to add these agents
    # agents.append(create_outline_generator_agent())
    # 
    # if not without_critics:
    #     agents.append(create_outline_critic())
    # 
    # agents.append(create_slide_and_script_generator_agent())
    # 
    # if not without_critics:
    #     agents.append(create_slides_critic())
    # 
    # if not without_critics:
    #     agents.append(create_script_critic())
    
    return SequentialAgent(
        name="SimplePresentationPipeline",
        description="Simplified presentation generation pipeline - currently only report understanding",
        sub_agents=agents,
    )

