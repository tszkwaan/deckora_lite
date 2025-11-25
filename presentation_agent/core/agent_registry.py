"""
Agent registry for dependency injection.
Extracted from PipelineOrchestrator to follow Dependency Inversion Principle.
"""

from typing import Dict, Any, Optional, Protocol
from abc import ABC


class AgentProtocol(Protocol):
    """
    Protocol defining the interface for agents.
    ADK agents should conform to this interface.
    """
    name: str


class AgentRegistry:
    """
    Registry for managing agent instances.
    Provides a centralized way to access and manage agents.
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._agents: Dict[str, Any] = {}
    
    def register(self, name: str, agent: Any) -> None:
        """
        Register an agent with the registry.
        
        Args:
            name: Agent name/identifier
            agent: Agent instance (should conform to AgentProtocol)
        """
        self._agents[name] = agent
    
    def get(self, name: str) -> Any:
        """
        Get an agent by name.
        
        Args:
            name: Agent name/identifier
        
        Returns:
            Agent instance
        
        Raises:
            KeyError: If agent not found
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not found in registry. Available agents: {list(self._agents.keys())}")
        return self._agents[name]
    
    def has(self, name: str) -> bool:
        """
        Check if an agent is registered.
        
        Args:
            name: Agent name/identifier
        
        Returns:
            True if agent is registered, False otherwise
        """
        return name in self._agents
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all registered agents.
        
        Returns:
            Dictionary mapping agent names to agent instances
        """
        return self._agents.copy()


def create_default_agent_registry() -> AgentRegistry:
    """
    Create and populate the default agent registry with all pipeline agents.
    
    Returns:
        AgentRegistry instance with all agents registered
    """
    registry = AgentRegistry()
    
    # Import agents (lazy import to avoid circular dependencies)
    from presentation_agent.agents.report_understanding_agent.agent import agent as report_understanding_agent
    from presentation_agent.agents.outline_generator_agent.agent import agent as outline_generator_agent
    from presentation_agent.agents.outline_critic_agent.agent import agent as outline_critic_agent
    from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_and_script_generator_agent
    from presentation_agent.agents.chart_generator_agent.agent import agent as chart_generator_agent
    
    # Register all agents
    registry.register("report_understanding", report_understanding_agent)
    registry.register("outline_generator", outline_generator_agent)
    registry.register("outline_critic", outline_critic_agent)
    registry.register("slide_and_script_generator", slide_and_script_generator_agent)
    registry.register("chart_generator", chart_generator_agent)
    
    return registry

