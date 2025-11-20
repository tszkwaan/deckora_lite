"""
State Access Tool for ADK Agents.

✅ BEST PRACTICE: Reference-based data access
- Allows agents to read from session.state without duplicating data in messages
- Reduces token usage by avoiding data duplication
- Follows ADK best practices: agents access state through tools, not direct access
"""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def get_state_value_tool(key: str) -> Dict[str, Any]:
    """
    Tool function to read a value from session.state.
    
    ✅ BEST PRACTICE: Reference-based data access
    This tool allows agents to access session.state without duplicating data in messages.
    Use this when agent instructions reference session.state['key'].
    
    Args:
        key: The key to read from session.state (e.g., 'report_knowledge', 'presentation_outline')
        
    Returns:
        Dict with keys:
            - status: "success" or "error"
            - value: The value from session.state (if success)
            - error: Error message (if error)
            
    Example:
        >>> result = get_state_value_tool("report_knowledge")
        >>> if result["status"] == "success":
        ...     report_knowledge = result["value"]
    """
    # NOTE: In ADK, tools don't have direct access to session.state
    # This tool is a placeholder that agents can call, but the actual state access
    # needs to be handled at the orchestration layer (main.py) or through callbacks.
    # 
    # For now, we'll return an error indicating that agents should receive data
    # through their input messages, but we keep this tool for future ADK enhancements.
    
    logger.warning(f"⚠️ get_state_value_tool called with key='{key}', but ADK tools cannot directly access session.state")
    logger.warning("   This tool is kept for future ADK enhancements. For now, data should be passed via input messages.")
    
    return {
        "status": "error",
        "error": f"Direct session.state access not available in ADK tools. Key '{key}' should be provided in input message.",
        "message": "In ADK, agents receive data through input messages, not direct state access. Please ensure the data is included in your input message."
    }


def get_state_value_tool_with_context(key: str, invocation_context: Any = None) -> Dict[str, Any]:
    """
    Tool function to read a value from session.state (with context injection).
    
    This is a helper function that can be used in callbacks or orchestration layer
    where we have access to invocation_context.
    
    Args:
        key: The key to read from session.state
        invocation_context: ADK invocation context (optional, for internal use)
        
    Returns:
        Dict with status, value, and error keys
    """
    if invocation_context is None:
        return get_state_value_tool(key)
    
    # Try to access state from invocation context
    state = None
    if hasattr(invocation_context, 'state'):
        state = invocation_context.state
    elif hasattr(invocation_context, 'session') and hasattr(invocation_context.session, 'state'):
        state = invocation_context.session.state
    
    if state is None:
        return {
            "status": "error",
            "error": f"Could not access session.state. Key '{key}' not found.",
            "message": "State access failed"
        }
    
    # Try multiple methods to get value
    value = None
    if hasattr(state, 'get'):
        value = state.get(key)
    elif hasattr(state, key):
        value = getattr(state, key)
    elif hasattr(state, '__dict__'):
        value = state.__dict__.get(key)
    elif isinstance(state, dict):
        value = state.get(key)
    
    if value is None:
        return {
            "status": "error",
            "error": f"Key '{key}' not found in session.state",
            "message": f"Available keys: {list(state.keys()) if hasattr(state, 'keys') else 'unknown'}"
        }
    
    logger.info(f"✅ Retrieved '{key}' from session.state")
    return {
        "status": "success",
        "value": value,
        "key": key
    }

