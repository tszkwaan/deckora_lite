"""
Retry logic handler.
Extracted from main.py to follow Single Responsibility Principle.
"""

import logging
from typing import Callable, Any, Optional, Dict, Tuple
from config import LAYOUT_MAX_RETRY_LOOPS, OUTLINE_MAX_RETRY_LOOPS

logger = logging.getLogger(__name__)


class RetryHandler:
    """
    Handles retry logic for agent execution with quality checks.
    """
    
    def __init__(
        self,
        max_retries: int,
        check_fn: Optional[Callable[[Any], Tuple[bool, Dict]]] = None,
        retry_callback: Optional[Callable[[int, str], None]] = None
    ):
        """
        Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            check_fn: Function to check if output passes (returns (passed, details))
            retry_callback: Optional callback for logging retries
        """
        self.max_retries = max_retries
        self.check_fn = check_fn
        self.retry_callback = retry_callback
    
    async def execute_with_retry(
        self,
        execute_fn: Callable[[], Any],
        retry_message_fn: Optional[Callable[[int, str], str]] = None
    ) -> Optional[Any]:
        """
        Execute a function with retry logic.
        
        Args:
            execute_fn: Async function that returns the output to check
            retry_message_fn: Optional function to generate retry message from feedback
            
        Returns:
            Output from execute_fn, or None if all retries failed
        """
        retries = 0
        
        while retries <= self.max_retries:
            if retries > 0:
                logger.info(f"Retry attempt {retries}/{self.max_retries}")
                if self.retry_callback:
                    self.retry_callback(retries, "Retrying...")
            
            output = await execute_fn()
            
            if output is None:
                retries += 1
                continue
            
            # If no check function, return output immediately
            if self.check_fn is None:
                return output
            
            # Check if output passes
            passed, details = self.check_fn(output)
            
            if passed:
                return output
            
            # Prepare for retry
            failure_reasons = details.get('failure_reasons', ['Quality check failed'])
            feedback = '; '.join(failure_reasons)
            
            if retries >= self.max_retries:
                logger.warning(f"Max retries reached. Returning last output.")
                return output
            
            retries += 1
            
            if self.retry_callback:
                self.retry_callback(retries, feedback)
            
            # If retry_message_fn is provided, update the execution context
            if retry_message_fn:
                retry_message = retry_message_fn(retries, feedback)
                # Note: This assumes execute_fn can be modified to use retry_message
                # In practice, you'd need to pass this back to the caller
                logger.info(f"Retry message: {retry_message[:100]}...")
        
        return None


class OutlineRetryHandler(RetryHandler):
    """Specialized retry handler for outline generation."""
    
    def __init__(self, check_fn: Callable[[Any], Tuple[bool, Dict]], retry_callback: Optional[Callable] = None):
        super().__init__(
            max_retries=OUTLINE_MAX_RETRY_LOOPS,
            check_fn=check_fn,
            retry_callback=retry_callback
        )


class LayoutRetryHandler(RetryHandler):
    """Specialized retry handler for layout review."""
    
    def __init__(self, check_fn: Optional[Callable[[Any], tuple[bool, Dict]]] = None, retry_callback: Optional[Callable] = None):
        super().__init__(
            max_retries=LAYOUT_MAX_RETRY_LOOPS,
            check_fn=check_fn,
            retry_callback=retry_callback
        )

