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
    from presentation_agent.agent import root_agent
    
    # Try different import paths for AgentEngine
    AgentEngine = None
    AgentEngine_create = None
    
    # Try primary import path: aiplatform.AgentEngine
    try:
        # Based on web search: aiplatform.AgentEngine.create()
        if hasattr(aiplatform, 'AgentEngine'):
            AgentEngine_create = aiplatform.AgentEngine.create
            print("✅ Found AgentEngine at: aiplatform.AgentEngine")
        else:
            raise AttributeError("aiplatform.AgentEngine not found")
    except (AttributeError, ImportError) as e1:
        # Try alternative: google.adk.agent_engines
        try:
            from google.adk.agent_engines import AgentEngine
            print("✅ Found AgentEngine at: google.adk.agent_engines")
        except ImportError as e2:
            # Try: google.cloud.aiplatform.agent_engines
            try:
                from google.cloud.aiplatform.agent_engines import AgentEngine
                print("✅ Found AgentEngine at: google.cloud.aiplatform.agent_engines")
            except ImportError as e3:
                print("❌ Could not find AgentEngine in standard locations")
                print(f"   Error 1: {e1}")
                print(f"   Error 2: {e2}")
                print(f"   Error 3: {e3}")
                print("\nTrying alternative deployment method...")
                # Try using ADK's deploy command directly via CLI
                AgentEngine = "CLI_FALLBACK"
            
except ImportError as e:
    print(f"❌ Error importing required modules: {e}")
    print("\nPlease ensure you have installed:")
    print("  pip install google-cloud-aiplatform[agent_engines,adk]")
    print("  pip install google-adk")
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
        if AgentEngine is None:
            print("\n❌ AgentEngine class not found!")
            print("\nPlease check the ADK documentation for the correct import path:")
            print("  https://google.github.io/adk-docs/deploy/agent-engine/")
            print("\nOr try installing/upgrading:")
            print("  pip install --upgrade google-cloud-aiplatform[agent_engines,adk]")
            print("  pip install --upgrade google-adk")
            sys.exit(1)
        
        if AgentEngine == "CLI_FALLBACK":
            # Use ADK CLI command as fallback
            print("\n⚠️ Using ADK CLI fallback method...")
            import subprocess
            import json
            import os
            
            # Check adk deploy command structure
            try:
                help_result = subprocess.run(
                    ["adk", "deploy", "--help"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                print("ADK deploy help:")
                print(help_result.stdout)
                if help_result.stderr:
                    print("ADK deploy stderr:")
                    print(help_result.stderr)
            except Exception as e:
                print(f"Could not get adk deploy help: {e}")
            
            # Try using adk deploy agent-engine command
            # Create a temporary requirements file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write('\n'.join(requirements))
                req_file = f.name
            
            agent_path = str(project_root / "presentation_agent")
            
            try:
                # Try different command formats
                # Format 1: adk deploy agent-engine
                cmd_options = [
                    # Option 1: Try with agent-engine subcommand (correct syntax)
                    ["adk", "deploy", "agent-engine", agent_path, "--name", agent_name, "--project", project_id, "--location", location, "--requirements", req_file],
                    # Option 1b: Try with agent_engine (underscore)
                    ["adk", "deploy", "agent_engine", agent_path, "--name", agent_name, "--project", project_id, "--location", location, "--requirements", req_file],
                    # Option 2: Try without subcommand but with different flags
                    ["adk", "deploy", agent_path, "--name", agent_name, "--project", project_id, "--region", location, "--requirements", req_file],
                    # Option 3: Try minimal command
                    ["adk", "deploy", agent_path, "--project", project_id],
                ]
                
                for i, cmd in enumerate(cmd_options, 1):
                    print(f"\nTrying command format {i}: {' '.join(cmd)}")
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            check=True,
                            cwd=project_root
                        )
                        print("✅ Success!")
                        print(result.stdout)
                        if result.stderr:
                            print("stderr:", result.stderr)
                        return {"status": "deployed", "method": f"cli_format_{i}"}
                    except subprocess.CalledProcessError as e:
                        print(f"❌ Format {i} failed (exit code {e.returncode})")
                        if e.stdout:
                            print(f"stdout: {e.stdout}")
                        if e.stderr:
                            print(f"stderr: {e.stderr}")
                        if i < len(cmd_options):
                            print("Trying next format...")
                            continue
                        else:
                            raise
                            
            except Exception as e:
                print(f"\n❌ All CLI deployment attempts failed: {e}")
                print("\n💡 Manual deployment option:")
                print("You can deploy manually using:")
                print(f"  cd {agent_path}")
                print(f"  adk deploy --help  # Check available options")
                print(f"  # Then use the correct adk deploy command syntax")
                raise
            finally:
                if os.path.exists(req_file):
                    os.unlink(req_file)
        elif AgentEngine_create is not None:
            # Use aiplatform.AgentEngine.create() method (recommended)
            print(f"\n📦 Creating AgentEngine using aiplatform.AgentEngine.create()...")
            deployed_agent = AgentEngine_create(
                local_agent=root_agent,
                requirements=requirements,
                display_name=agent_name,
                description="Presentation generation agent from research reports",
            )
            
            print(f"\n✅ Agent deployed successfully!")
            if hasattr(deployed_agent, 'resource_name'):
                print(f"   Agent Resource Name: {deployed_agent.resource_name}")
            if hasattr(deployed_agent, 'agent_id'):
                print(f"   Agent ID: {deployed_agent.agent_id}")
            if hasattr(deployed_agent, 'name'):
                print(f"   Agent Name: {deployed_agent.name}")
            
            return deployed_agent
        else:
            # Use AgentEngine class (if found)
            print(f"\n📦 Creating AgentEngine instance...")
            agent_engine = AgentEngine(
                agent=root_agent,
                agent_name=agent_name,
                requirements=requirements,
            )
            
            print(f"🚀 Deploying agent...")
            # Deploy the agent
            deployed_agent = agent_engine.deploy()
            
            print(f"\n✅ Agent deployed successfully!")
            if hasattr(deployed_agent, 'resource_name'):
                print(f"   Agent Resource Name: {deployed_agent.resource_name}")
            if hasattr(deployed_agent, 'agent_id'):
                print(f"   Agent ID: {deployed_agent.agent_id}")
            if hasattr(deployed_agent, 'name'):
                print(f"   Agent Name: {deployed_agent.name}")
            
            return deployed_agent
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Troubleshooting tips:")
        print("1. Verify Vertex AI API is enabled")
        print("2. Check service account has Vertex AI User role")
        print("3. Ensure all dependencies are installed")
        print("4. Check ADK documentation for latest deployment API")
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

