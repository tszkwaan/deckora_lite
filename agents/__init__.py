"""
Agents package for presentation generation pipeline.
"""

from agents.report_understanding import create_report_understanding_agent
from agents.style_extractor import create_style_extractor_agent
from agents.outline_generator import create_outline_generator_agent
from agents.slide_generator import create_slide_generator_agent
from agents.script_generator import create_script_generator_agent
from agents.critic import (
    create_critic_agent,
    create_outline_critic,
    create_slides_critic,
    create_script_critic,
)
from agents.slideshow_exporter import create_slideshow_exporter_agent
from agents.orchestrator import (
    create_presentation_pipeline,
    create_simple_pipeline,
)

__all__ = [
    "create_report_understanding_agent",
    "create_style_extractor_agent",
    "create_outline_generator_agent",
    "create_slide_generator_agent",
    "create_script_generator_agent",
    "create_critic_agent",
    "create_outline_critic",
    "create_slides_critic",
    "create_script_critic",
    "create_slideshow_exporter_agent",
    "create_presentation_pipeline",
    "create_simple_pipeline",
]

