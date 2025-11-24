"""
Standardized logging utilities for consistent error and info logging across the pipeline.
Provides structured logging with consistent message formats.
"""

import logging
from typing import Optional, Dict, Any
from functools import wraps


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module/component.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_agent_error(
    logger: logging.Logger,
    message: str,
    agent_name: Optional[str] = None,
    output_key: Optional[str] = None,
    error: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an agent execution error with standardized format.
    
    Args:
        logger: Logger instance
        message: Error message
        agent_name: Name of the agent (optional)
        output_key: Expected output key (optional)
        error: Exception object (optional)
        context: Additional context dictionary (optional)
    """
    parts = []
    
    if agent_name:
        parts.append(f"[{agent_name}]")
    
    parts.append(message)
    
    if output_key:
        parts.append(f"(output_key: '{output_key}')")
    
    if error:
        parts.append(f"Error: {type(error).__name__}: {str(error)}")
    
    log_message = " ".join(parts)
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message += f" | Context: {context_str}"
    
    logger.error(log_message)


def log_agent_warning(
    logger: logging.Logger,
    message: str,
    agent_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an agent warning with standardized format.
    
    Args:
        logger: Logger instance
        message: Warning message
        agent_name: Name of the agent (optional)
        context: Additional context dictionary (optional)
    """
    parts = []
    
    if agent_name:
        parts.append(f"[{agent_name}]")
    
    parts.append(message)
    
    log_message = " ".join(parts)
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message += f" | Context: {context_str}"
    
    logger.warning(log_message)


def log_agent_info(
    logger: logging.Logger,
    message: str,
    agent_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an agent info message with standardized format.
    
    Args:
        logger: Logger instance
        message: Info message
        agent_name: Name of the agent (optional)
        context: Additional context dictionary (optional)
    """
    parts = []
    
    if agent_name:
        parts.append(f"[{agent_name}]")
    
    parts.append(message)
    
    log_message = " ".join(parts)
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message += f" | Context: {context_str}"
    
    logger.info(log_message)


def log_agent_debug(
    logger: logging.Logger,
    message: str,
    agent_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an agent debug message with standardized format.
    
    Args:
        logger: Logger instance
        message: Debug message
        agent_name: Name of the agent (optional)
        context: Additional context dictionary (optional)
    """
    parts = []
    
    if agent_name:
        parts.append(f"[{agent_name}]")
    
    parts.append(message)
    
    log_message = " ".join(parts)
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message += f" | Context: {context_str}"
    
    logger.debug(log_message)


def log_component_error(
    logger: logging.Logger,
    message: str,
    component: Optional[str] = None,
    error: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a component error with standardized format.
    
    Args:
        logger: Logger instance
        message: Error message
        component: Component name (optional)
        error: Exception object (optional)
        context: Additional context dictionary (optional)
    """
    parts = []
    
    if component:
        parts.append(f"[{component}]")
    
    parts.append(message)
    
    if error:
        parts.append(f"Error: {type(error).__name__}: {str(error)}")
    
    log_message = " ".join(parts)
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message += f" | Context: {context_str}"
    
    logger.error(log_message)


def log_component_warning(
    logger: logging.Logger,
    message: str,
    component: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a component warning with standardized format.
    
    Args:
        logger: Logger instance
        message: Warning message
        component: Component name (optional)
        context: Additional context dictionary (optional)
    """
    parts = []
    
    if component:
        parts.append(f"[{component}]")
    
    parts.append(message)
    
    log_message = " ".join(parts)
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message += f" | Context: {context_str}"
    
    logger.warning(log_message)


def log_component_info(
    logger: logging.Logger,
    message: str,
    component: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a component info message with standardized format.
    
    Args:
        logger: Logger instance
        message: Info message
        component: Component name (optional)
        context: Additional context dictionary (optional)
    """
    parts = []
    
    if component:
        parts.append(f"[{component}]")
    
    parts.append(message)
    
    log_message = " ".join(parts)
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message += f" | Context: {context_str}"
    
    logger.info(log_message)


def log_json_parse_error(
    logger: logging.Logger,
    message: str,
    agent_name: Optional[str] = None,
    output_key: Optional[str] = None,
    raw_output_preview: Optional[str] = None,
    error: Optional[Exception] = None
) -> None:
    """
    Log a JSON parsing error with standardized format.
    
    Args:
        logger: Logger instance
        message: Error message
        agent_name: Name of the agent (optional)
        output_key: Expected output key (optional)
        raw_output_preview: Preview of raw output that failed to parse (optional)
        error: Exception object (optional)
    """
    parts = []
    
    if agent_name:
        parts.append(f"[{agent_name}]")
    
    parts.append(f"JSON Parse Error: {message}")
    
    if output_key:
        parts.append(f"(output_key: '{output_key}')")
    
    if error:
        parts.append(f"Error: {type(error).__name__}: {str(error)}")
    
    log_message = " ".join(parts)
    
    if raw_output_preview:
        preview = raw_output_preview[:500] if len(raw_output_preview) > 500 else raw_output_preview
        log_message += f" | Raw output preview: {preview}"
    
    logger.error(log_message)

