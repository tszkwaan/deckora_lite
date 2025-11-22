"""
Custom exceptions for consistent error handling across the pipeline.
"""


class AgentExecutionError(Exception):
    """Base exception for agent execution failures."""
    
    def __init__(self, message: str, agent_name: str = None, output_key: str = None):
        """
        Initialize agent execution error.
        
        Args:
            message: Error message
            agent_name: Name of the agent that failed (optional)
            output_key: Expected output key that was missing (optional)
        """
        self.agent_name = agent_name
        self.output_key = output_key
        if agent_name:
            full_message = f"[{agent_name}] {message}"
            if output_key:
                full_message += f" (output_key: '{output_key}')"
        else:
            full_message = message
        super().__init__(full_message)


class JSONParseError(AgentExecutionError):
    """Raised when agent output cannot be parsed as JSON."""
    
    def __init__(self, message: str, agent_name: str = None, output_key: str = None, raw_output: str = None):
        """
        Initialize JSON parse error.
        
        Args:
            message: Error message
            agent_name: Name of the agent that failed (optional)
            output_key: Expected output key that failed to parse (optional)
            raw_output: Raw output that failed to parse (optional, for debugging)
        """
        self.raw_output = raw_output
        super().__init__(message, agent_name, output_key)


class AgentOutputError(AgentExecutionError):
    """Raised when agent output is missing required fields or has invalid structure."""
    
    def __init__(self, message: str, agent_name: str = None, output_key: str = None, available_keys: list = None):
        """
        Initialize agent output error.
        
        Args:
            message: Error message
            agent_name: Name of the agent that failed (optional)
            output_key: Expected output key (optional)
            available_keys: List of available keys in the output (optional)
        """
        self.available_keys = available_keys
        if available_keys:
            message += f" Available keys: {available_keys}"
        super().__init__(message, agent_name, output_key)

