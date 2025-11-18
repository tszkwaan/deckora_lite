"""
Quality check utilities for evaluating outline confidence scores.
"""

from typing import Dict, Any, Optional, Tuple
from config import OUTLINE_HALLUCINATION_THRESHOLD, OUTLINE_SAFETY_THRESHOLD, OUTLINE_MAX_RETRY_LOOPS


def check_outline_quality(critic_review: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if outline passes quality thresholds based on critic review.
    
    Args:
        critic_review: The critic review output containing hallucination_check and safety_check
                      Can be a dict or a string (will be parsed)
        
    Returns:
        Tuple of (passed: bool, details: dict)
        - passed: True if all thresholds are met, False otherwise
        - details: Dictionary with score breakdown and reasons for failure
    """
    if not critic_review:
        return False, {
            "error": "No critic review provided",
            "hallucination_score": None,
            "safety_score": None,
        }
    
    # Handle string input (if JSON wasn't parsed yet)
    if isinstance(critic_review, str):
        try:
            import json
            # Try to parse as JSON
            critic_review = json.loads(critic_review)
        except (json.JSONDecodeError, ValueError):
            return False, {
                "error": "Critic review is a string but not valid JSON",
                "hallucination_score": None,
                "safety_score": None,
            }
    
    # Ensure it's a dict
    if not isinstance(critic_review, dict):
        return False, {
            "error": f"Critic review must be a dict, got {type(critic_review).__name__}",
            "hallucination_score": None,
            "safety_score": None,
        }
    
    hallucination_check = critic_review.get("hallucination_check", {})
    safety_check = critic_review.get("safety_check", {})
    
    # Extract scores (handle both string and numeric formats)
    hallucination_score = _extract_score(hallucination_check.get("score"))
    safety_score = _extract_score(safety_check.get("score"))
    
    # Check thresholds
    hallucination_passed = hallucination_score is not None and hallucination_score >= OUTLINE_HALLUCINATION_THRESHOLD
    safety_passed = safety_score is not None and safety_score >= OUTLINE_SAFETY_THRESHOLD
    
    passed = hallucination_passed and safety_passed
    
    details = {
        "hallucination_score": hallucination_score,
        "hallucination_threshold": OUTLINE_HALLUCINATION_THRESHOLD,
        "hallucination_passed": hallucination_passed,
        "safety_score": safety_score,
        "safety_threshold": OUTLINE_SAFETY_THRESHOLD,
        "safety_passed": safety_passed,
        "overall_passed": passed,
        "failure_reasons": [],
    }
    
    if not hallucination_passed:
        if hallucination_score is not None:
            details["failure_reasons"].append(
                f"Hallucination score {hallucination_score:.2f} below threshold {OUTLINE_HALLUCINATION_THRESHOLD:.2f}"
            )
        else:
            details["failure_reasons"].append(
                f"Hallucination score not found in critic review (threshold: {OUTLINE_HALLUCINATION_THRESHOLD:.2f})"
            )
    if not safety_passed:
        if safety_score is not None:
            details["failure_reasons"].append(
                f"Safety score {safety_score:.2f} below threshold {OUTLINE_SAFETY_THRESHOLD:.2f}"
            )
        else:
            details["failure_reasons"].append(
                f"Safety score not found in critic review (threshold: {OUTLINE_SAFETY_THRESHOLD:.2f})"
            )
    
    return passed, details


def _extract_score(score_value: Any) -> Optional[float]:
    """
    Extract numeric score from various formats.
    
    Handles:
    - Numeric values (float/int)
    - String representations of numbers
    - String descriptions that might contain numbers
    """
    if score_value is None:
        return None
    
    if isinstance(score_value, (int, float)):
        return float(score_value)
    
    if isinstance(score_value, str):
        # Try to extract number from string
        try:
            # Remove any non-numeric characters except decimal point
            cleaned = ''.join(c for c in score_value if c.isdigit() or c == '.')
            if cleaned:
                return float(cleaned)
        except (ValueError, AttributeError):
            pass
        
        # Try direct conversion
        try:
            return float(score_value)
        except (ValueError, TypeError):
            pass
    
    return None


def create_quality_log_entry(
    attempt: int,
    passed: bool,
    details: Dict[str, Any],
    max_attempts: int = OUTLINE_MAX_RETRY_LOOPS,
) -> Dict[str, Any]:
    """
    Create a log entry for quality check results.
    
    Args:
        attempt: Current attempt number (1-indexed)
        passed: Whether the quality check passed
        details: Quality check details from check_outline_quality
        max_attempts: Maximum number of attempts allowed
        
    Returns:
        Dictionary with log entry information
    """
    log_entry = {
        "attempt": attempt,
        "max_attempts": max_attempts,
        "passed": passed,
        "timestamp": None,  # Can be filled in by caller
        **details,
    }
    
    if attempt >= max_attempts and not passed:
        log_entry["status"] = "max_loops_reached"
        log_entry["action"] = "proceeding_with_low_quality"
        log_entry["warning"] = f"Outline quality below threshold after {max_attempts} attempts. Proceeding with current outline."
    elif passed:
        log_entry["status"] = "passed"
        log_entry["action"] = "proceeding"
    else:
        log_entry["status"] = "retrying"
        log_entry["action"] = "regenerating_outline"
    
    return log_entry

