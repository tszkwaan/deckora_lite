"""
Deploy agent to Vertex AI Agent Engine.
This script deploys the presentation agent to Vertex AI Agent Engine using ADK.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from google.cloud import aiplatform
    # Try different import paths for AgentEngine
    try:
        from google.adk.agent_engines import AgentEngine
    except ImportError:
        try:
            from google.cloud.aiplatform.agent_engines import AgentEngine
        except ImportError:
            # Fallback: use ADK's deployment utilities
            from google.adk.deployment import deploy_agent as adk_deploy_agent
            AgentEngine = None
    from presentation_agent.agent import root_agent
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please install: pip install google-cloud-aiplatform[agent_engines,adk]")
    sys.exit(1)


def deploy_agent(
    project_id: str,
    location: str = "us-central1",
    agent_name: str = "presentation-agent",
    requirements: list = None
):
    """
    Deploy the presentation agent to Vertex AI Agent Engine.
    
    Args:
        project_id: Google Cloud project ID
        location: GCP region (default: us-central1)
        agent_name: Name for the deployed agent
        requirements: List of additional Python packages required
    """
    # Initialize Vertex AI
    aiplatform.init(project=project_id, location=location)
    
    # Default requirements
    if requirements is None:
        requirements = [
            "google-adk[eval]",
            "google-genai",
            "pypdf",
            "requests",
            "python-dotenv",
            "google-api-python-client>=2.0.0",
            "google-auth-httplib2>=0.1.0",
            "google-auth-oauthlib>=1.0.0",
            "google-cloud-vision>=3.0.0",
            "pdf2image>=1.16.0",
            "Pillow>=10.0.0",
        ]
    
    print(f"🚀 Deploying agent '{agent_name}' to Vertex AI Agent Engine...")
    print(f"   Project: {project_id}")
    print(f"   Location: {location}")
    print(f"   Requirements: {len(requirements)} packages")
    
    try:
        if AgentEngine is not None:
            # Use AgentEngine class
            agent_engine = AgentEngine(
                agent=root_agent,
                agent_name=agent_name,
                requirements=requirements,
            )
            
            # Deploy the agent
            deployed_agent = agent_engine.deploy()
            
            print(f"✅ Agent deployed successfully!")
            if hasattr(deployed_agent, 'resource_name'):
                print(f"   Agent Resource Name: {deployed_agent.resource_name}")
            if hasattr(deployed_agent, 'agent_id'):
                print(f"   Agent ID: {deployed_agent.agent_id}")
            if hasattr(deployed_agent, 'name'):
                print(f"   Agent Name: {deployed_agent.name}")
            
            return deployed_agent
        else:
            # Fallback: use ADK deployment function directly
            print("⚠️ Using fallback deployment method...")
            deployed_agent = adk_deploy_agent(
                agent=root_agent,
                agent_name=agent_name,
                project_id=project_id,
                location=location,
                requirements=requirements
            )
            print(f"✅ Agent deployed successfully!")
            return deployed_agent
        
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy agent to Vertex AI Agent Engine")
    parser.add_argument(
        "--project-id",
        required=True,
        help="Google Cloud project ID"
    )
    parser.add_argument(
        "--location",
        default="us-central1",
        help="GCP region (default: us-central1)"
    )
    parser.add_argument(
        "--agent-name",
        default="presentation-agent",
        help="Name for the deployed agent (default: presentation-agent)"
    )
    
    args = parser.parse_args()
    
    deploy_agent(
        project_id=args.project_id,
        location=args.location,
        agent_name=args.agent_name
    )

