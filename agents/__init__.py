"""
Agents package for presentation generation pipeline.
"""

from .report_understanding import create_report_understanding_agent
from .outline_generator import create_outline_generator_agent
from .slide_and_script_generator import create_slide_and_script_generator_agent
from .critic import (
    create_critic_agent,
    create_outline_critic,
    create_slides_critic,
    create_script_critic,
)
from .layout_critic import create_layout_critic_agent
from .orchestrator import (
    create_presentation_pipeline,
    create_simple_pipeline,
)

__all__ = [
    "create_report_understanding_agent",
    "create_outline_generator_agent",
    "create_slide_and_script_generator_agent",
    "create_critic_agent",
    "create_outline_critic",
    "create_slides_critic",
    "create_script_critic",
    "create_layout_critic_agent",
    "create_presentation_pipeline",
    "create_simple_pipeline",
]

