"""
Observability module for tracking agent execution, metrics, and traces.
Provides structured logging, execution tracing, and metrics collection.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum


class AgentStatus(Enum):
    """Status of an agent execution."""
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    SKIPPED = "skipped"


@dataclass
class AgentExecution:
    """Represents a single agent execution."""
    agent_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    status: AgentStatus = AgentStatus.SUCCESS
    retry_count: int = 0
    error_message: Optional[str] = None
    output_key: Optional[str] = None
    has_output: bool = False
    
    def finish(self, status: AgentStatus = AgentStatus.SUCCESS, error_message: Optional[str] = None):
        """Mark execution as finished."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        self.status = status
        if error_message:
            self.error_message = error_message
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['status'] = self.status.value
        return result


@dataclass
class PipelineMetrics:
    """Metrics for the entire pipeline execution."""
    pipeline_start_time: float
    pipeline_end_time: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    total_agents_executed: int = 0
    successful_agents: int = 0
    failed_agents: int = 0
    retried_agents: int = 0
    total_retries: int = 0
    agents_executions: List[AgentExecution] = field(default_factory=list)
    
    def add_execution(self, execution: AgentExecution):
        """Add an agent execution to metrics."""
        self.agents_executions.append(execution)
        self.total_agents_executed += 1
        
        if execution.status == AgentStatus.SUCCESS:
            self.successful_agents += 1
        elif execution.status == AgentStatus.FAILED:
            self.failed_agents += 1
        elif execution.status == AgentStatus.RETRY:
            self.retried_agents += 1
        
        if execution.retry_count > 0:
            self.total_retries += execution.retry_count
    
    def finish(self):
        """Mark pipeline as finished."""
        self.pipeline_end_time = time.time()
        self.total_duration_seconds = self.pipeline_end_time - self.pipeline_start_time
    
    def get_success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.total_agents_executed == 0:
            return 0.0
        return self.successful_agents / self.total_agents_executed
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'pipeline_start_time': self.pipeline_start_time,
            'pipeline_end_time': self.pipeline_end_time,
            'total_duration_seconds': self.total_duration_seconds,
            'total_agents_executed': self.total_agents_executed,
            'successful_agents': self.successful_agents,
            'failed_agents': self.failed_agents,
            'retried_agents': self.retried_agents,
            'total_retries': self.total_retries,
            'success_rate': self.get_success_rate(),
            'agents_executions': [exec.to_dict() for exec in self.agents_executions]
        }


class ObservabilityLogger:
    """Main observability logger for tracking agent executions and metrics."""
    
    def __init__(self, log_file: str = "observability.log", trace_file: Optional[str] = None):
        """
        Initialize observability logger.
        
        Args:
            log_file: Path to structured log file
            trace_file: Path to trace history JSON file (optional)
        """
        self.log_file = log_file
        self.trace_file = trace_file
        self.metrics: Optional[PipelineMetrics] = None
        self.current_execution: Optional[AgentExecution] = None
        
        # Set up structured logger
        self.logger = logging.getLogger("observability")
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create file handler for structured logging
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        
        # Structured format: timestamp | level | agent_name | message | data
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(data)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Also add console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def start_pipeline(self, pipeline_name: str = "presentation_pipeline"):
        """Start tracking a new pipeline execution."""
        self.metrics = PipelineMetrics(pipeline_start_time=time.time())
        self.logger.info(
            f"Pipeline started: {pipeline_name}",
            extra={'data': json.dumps({'pipeline_name': pipeline_name, 'start_time': datetime.now().isoformat()})}
        )
    
    def start_agent_execution(self, agent_name: str, output_key: Optional[str] = None, retry_count: int = 0):
        """
        Start tracking an agent execution.
        
        Args:
            agent_name: Name of the agent
            output_key: Expected output key from the agent
            retry_count: Number of retries (0 for first attempt)
            
        Returns:
            AgentExecution object
        """
        # Finish previous execution if still running
        if self.current_execution and self.current_execution.end_time is None:
            self.current_execution.finish(AgentStatus.SKIPPED, "Replaced by new execution")
        
        self.current_execution = AgentExecution(
            agent_name=agent_name,
            start_time=time.time(),
            retry_count=retry_count,
            output_key=output_key
        )
        
        self.logger.info(
            f"Agent execution started: {agent_name}",
            extra={'data': json.dumps({
                'agent_name': agent_name,
                'output_key': output_key,
                'retry_count': retry_count,
                'start_time': datetime.now().isoformat()
            })}
        )
        
        return self.current_execution
    
    def finish_agent_execution(
        self,
        status: AgentStatus = AgentStatus.SUCCESS,
        error_message: Optional[str] = None,
        has_output: bool = True
    ):
        """
        Finish tracking the current agent execution.
        
        Args:
            status: Execution status
            error_message: Error message if failed
            has_output: Whether the agent produced output
        """
        if not self.current_execution:
            self.logger.warning(
                "Attempted to finish agent execution but none is active",
                extra={'data': json.dumps({})}
            )
            return
        
        self.current_execution.finish(status, error_message)
        self.current_execution.has_output = has_output
        
        # Add to metrics
        if self.metrics:
            self.metrics.add_execution(self.current_execution)
        
        # Log completion
        log_data = {
            'agent_name': self.current_execution.agent_name,
            'duration_seconds': self.current_execution.duration_seconds,
            'status': status.value,
            'retry_count': self.current_execution.retry_count,
            'has_output': has_output
        }
        if error_message:
            log_data['error_message'] = error_message
        
        if status == AgentStatus.SUCCESS:
            self.logger.info(
                f"Agent execution completed: {self.current_execution.agent_name}",
                extra={'data': json.dumps(log_data)}
            )
        else:
            self.logger.warning(
                f"Agent execution finished with status {status.value}: {self.current_execution.agent_name}",
                extra={'data': json.dumps(log_data)}
            )
        
        self.current_execution = None
    
    def log_retry(self, agent_name: str, attempt: int, reason: str):
        """Log a retry attempt."""
        self.logger.info(
            f"Agent retry: {agent_name} (attempt {attempt})",
            extra={'data': json.dumps({
                'agent_name': agent_name,
                'attempt': attempt,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            })}
        )
    
    def finish_pipeline(self, save_trace: bool = True):
        """
        Finish tracking the pipeline and generate summary.
        
        Args:
            save_trace: Whether to save trace history to JSON file
            
        Returns:
            PipelineMetrics object
        """
        if not self.metrics:
            self.logger.warning(
                "Attempted to finish pipeline but none was started",
                extra={'data': json.dumps({})}
            )
            return None
        
        # Finish any remaining execution
        if self.current_execution and self.current_execution.end_time is None:
            self.current_execution.finish(AgentStatus.SKIPPED, "Pipeline finished")
            self.metrics.add_execution(self.current_execution)
        
        self.metrics.finish()
        
        # Log pipeline completion
        self.logger.info(
            "Pipeline completed",
            extra={'data': json.dumps({
                'total_duration_seconds': self.metrics.total_duration_seconds,
                'total_agents_executed': self.metrics.total_agents_executed,
                'successful_agents': self.metrics.successful_agents,
                'failed_agents': self.metrics.failed_agents,
                'total_retries': self.metrics.total_retries,
                'success_rate': self.metrics.get_success_rate()
            })}
        )
        
        # Save trace history if requested
        if save_trace and self.trace_file:
            self.save_trace_history()
        
        # Print metrics summary
        self.print_metrics_summary()
        
        return self.metrics
    
    def save_trace_history(self):
        """Save trace history to JSON file."""
        if not self.metrics or not self.trace_file:
            return
        
        trace_data = {
            'pipeline_metrics': self.metrics.to_dict(),
            'timestamp': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        # Ensure directory exists
        trace_path = Path(self.trace_file)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to file
        with open(trace_path, 'w') as f:
            json.dump(trace_data, f, indent=2, default=str)
        
        self.logger.info(
            f"Trace history saved to {self.trace_file}",
            extra={'data': json.dumps({'trace_file': self.trace_file})}
        )
    
    def print_metrics_summary(self):
        """Print a human-readable metrics summary."""
        if not self.metrics:
            return
        
        print("\n" + "=" * 60)
        print("📊 PIPELINE METRICS SUMMARY")
        print("=" * 60)
        print(f"Total Duration: {self.metrics.total_duration_seconds:.2f} seconds ({self.metrics.total_duration_seconds / 60:.2f} minutes)")
        print(f"Total Agents Executed: {self.metrics.total_agents_executed}")
        print(f"Successful: {self.metrics.successful_agents} ✅")
        print(f"Failed: {self.metrics.failed_agents} ❌")
        print(f"Retried: {self.metrics.retried_agents} 🔄")
        print(f"Total Retries: {self.metrics.total_retries}")
        print(f"Success Rate: {self.metrics.get_success_rate() * 100:.1f}%")
        print("\nAgent Execution Details:")
        print("-" * 60)
        
        for exec in self.metrics.agents_executions:
            status_icon = {
                AgentStatus.SUCCESS: "✅",
                AgentStatus.FAILED: "❌",
                AgentStatus.RETRY: "🔄",
                AgentStatus.SKIPPED: "⏭️"
            }.get(exec.status, "❓")
            
            retry_info = f" (retry {exec.retry_count})" if exec.retry_count > 0 else ""
            print(f"{status_icon} {exec.agent_name}{retry_info}: {exec.duration_seconds:.2f}s")
            if exec.error_message:
                # Only show "Error:" prefix for failed executions
                if exec.status == AgentStatus.FAILED:
                    print(f"   Error: {exec.error_message}")
                else:
                    # For success messages, just show the message without "Error:" prefix
                    print(f"   {exec.error_message}")
        
        print("=" * 60)
        print(f"📝 Structured logs: {self.log_file}")
        if self.trace_file:
            print(f"📊 Trace history: {self.trace_file}")
        print("=" * 60 + "\n")


# Global observability logger instance
_observability_logger: Optional[ObservabilityLogger] = None


def get_observability_logger(
    log_file: str = "observability.log",
    trace_file: Optional[str] = None
) -> ObservabilityLogger:
    """
    Get or create the global observability logger instance.
    
    Args:
        log_file: Path to structured log file
        trace_file: Path to trace history JSON file
        
    Returns:
        ObservabilityLogger instance
    """
    global _observability_logger
    if _observability_logger is None:
        _observability_logger = ObservabilityLogger(log_file=log_file, trace_file=trace_file)
    return _observability_logger


def reset_observability_logger():
    """Reset the global observability logger (useful for testing)."""
    global _observability_logger
    _observability_logger = None

