"""
Main script for local development and testing of the presentation generation pipeline.

Refactored following SOLID principles:
- Single Responsibility: Each class/module has one clear purpose
- Open/Closed: Extensible through inheritance and composition
- Liskov Substitution: Subclasses can replace base classes
- Interface Segregation: Focused interfaces
- Dependency Inversion: Depend on abstractions, not concretions
"""

import asyncio
from config import PresentationConfig
from presentation_agent.core.pipeline_orchestrator import PipelineOrchestrator
from presentation_agent.core.app_initializer import AppInitializer


async def main():
    """Main function for local development."""
    output_dir = "presentation_agent/output"
    
    # Initialize application (logging, environment, API key validation)
    initializer = AppInitializer(output_dir=output_dir)
    if not initializer.initialize():
        return
    
    # Example configuration
    # Note: target_audience is optional - if not provided (or set to None), LLM will infer from scenario and report
    config = PresentationConfig(
        scenario="company staff education",
        duration="10 minutes",
        target_audience="internal staff",  # Optional - can be None to let LLM infer from scenario and report contentho
        custom_instruction="",
        report_url="https://www.tal.sg/wshc/-/media/TAL/Wshc/Resources/Publications/WSH-Guidelines/Files/WSH_Guidelines_Cleaning_and_Custodial_Services.pdf",
        style_images=[],  # Add image URLs here if you have them
    )
    
    try:
        # Create and run pipeline orchestrator
        orchestrator = PipelineOrchestrator(
            config=config,
            output_dir=output_dir,
            include_critics=True,
            save_intermediate=True,
            open_browser=True,
        )
        
        outputs = await orchestrator.run()
        
        print("\n" + "=" * 60)
        print("🎉 Pipeline completed successfully!")
        print("=" * 60)
        print(f"\nGenerated outputs saved to '{output_dir}/' directory")
        print(f"Total outputs: {len(outputs)}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline aborted by user (KeyboardInterrupt)")
        raise
    except Exception as e:
        print(f"\n\n❌ Pipeline failed with error: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Program interrupted by user")
        exit(0)
