"""
Observability backends for different deployment environments.
Supports file-based logging (local dev) and Google Cloud Monitoring/Logging (production).
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from datetime import datetime

from .observability import AgentExecution, PipelineMetrics, AgentStatus


class ObservabilityBackend(ABC):
    """Abstract base class for observability backends."""
    
    @abstractmethod
    def log_agent_start(self, execution: AgentExecution):
        """Log when an agent execution starts."""
        pass
    
    @abstractmethod
    def log_agent_finish(self, execution: AgentExecution):
        """Log when an agent execution finishes."""
        pass
    
    @abstractmethod
    def log_retry(self, agent_name: str, attempt: int, reason: str):
        """Log a retry attempt."""
        pass
    
    @abstractmethod
    def log_pipeline_start(self, pipeline_name: str):
        """Log when a pipeline starts."""
        pass
    
    @abstractmethod
    def log_pipeline_finish(self, metrics: PipelineMetrics):
        """Log when a pipeline finishes."""
        pass
    
    @abstractmethod
    def save_trace_history(self, metrics: PipelineMetrics, trace_file: str):
        """Save trace history."""
        pass


class FileBackend(ObservabilityBackend):
    """File-based backend for local development."""
    
    def __init__(self, log_file: str = "observability.log"):
        self.log_file = log_file
        self.logger = logging.getLogger("observability.file")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(data)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def log_agent_start(self, execution: AgentExecution):
        self.logger.info(
            f"Agent execution started: {execution.agent_name}",
            extra={'data': json.dumps({
                'agent_name': execution.agent_name,
                'output_key': execution.output_key,
                'retry_count': execution.retry_count,
                'start_time': datetime.now().isoformat()
            })}
        )
    
    def log_agent_finish(self, execution: AgentExecution):
        log_data = {
            'agent_name': execution.agent_name,
            'duration_seconds': execution.duration_seconds,
            'status': execution.status.value,
            'retry_count': execution.retry_count,
            'has_output': execution.has_output
        }
        if execution.error_message:
            log_data['error_message'] = execution.error_message
        
        if execution.status == AgentStatus.SUCCESS:
            self.logger.info(
                f"Agent execution completed: {execution.agent_name}",
                extra={'data': json.dumps(log_data)}
            )
        else:
            self.logger.warning(
                f"Agent execution finished with status {execution.status.value}: {execution.agent_name}",
                extra={'data': json.dumps(log_data)}
            )
    
    def log_retry(self, agent_name: str, attempt: int, reason: str):
        self.logger.info(
            f"Agent retry: {agent_name} (attempt {attempt})",
            extra={'data': json.dumps({
                'agent_name': agent_name,
                'attempt': attempt,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            })}
        )
    
    def log_pipeline_start(self, pipeline_name: str):
        self.logger.info(
            f"Pipeline started: {pipeline_name}",
            extra={'data': json.dumps({
                'pipeline_name': pipeline_name,
                'start_time': datetime.now().isoformat()
            })}
        )
    
    def log_pipeline_finish(self, metrics: PipelineMetrics):
        self.logger.info(
            "Pipeline completed",
            extra={'data': json.dumps({
                'total_duration_seconds': metrics.total_duration_seconds,
                'total_agents_executed': metrics.total_agents_executed,
                'successful_agents': metrics.successful_agents,
                'failed_agents': metrics.failed_agents,
                'total_retries': metrics.total_retries,
                'success_rate': metrics.get_success_rate()
            })}
        )
    
    def save_trace_history(self, metrics: PipelineMetrics, trace_file: str):
        """Save trace history to JSON file."""
        from pathlib import Path
        
        trace_data = {
            'pipeline_metrics': metrics.to_dict(),
            'timestamp': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        trace_path = Path(trace_file)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(trace_path, 'w') as f:
            json.dump(trace_data, f, indent=2, default=str)
        
        self.logger.info(
            f"Trace history saved to {trace_file}",
            extra={'data': json.dumps({'trace_file': trace_file})}
        )


class GoogleCloudBackend(ObservabilityBackend):
    """Google Cloud Monitoring and Logging backend for production deployment."""
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize Google Cloud backend.
        
        Args:
            project_id: GCP project ID. If None, will try to detect from environment.
        """
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT')
        
        if not self.project_id:
            raise ValueError(
                "Google Cloud project ID not found. "
                "Set GOOGLE_CLOUD_PROJECT or GCP_PROJECT environment variable."
            )
        
        # Lazy import to avoid requiring google-cloud-logging/monitoring in local dev
        try:
            from google.cloud import logging as cloud_logging
            from google.cloud import monitoring_v3
            from google.cloud.monitoring_v3 import MetricServiceClient
            from google.cloud.monitoring_v3.types import TimeSeries
            
            self.cloud_logging = cloud_logging
            self.monitoring_v3 = monitoring_v3
            self.MetricServiceClient = MetricServiceClient
            self.TimeSeries = TimeSeries
            
            # Initialize Cloud Logging client
            self.logging_client = cloud_logging.Client(project=self.project_id)
            self.logger = self.logging_client.logger("presentation-agent")
            
            # Initialize Cloud Monitoring client
            self.monitoring_client = MetricServiceClient()
            self.project_name = f"projects/{self.project_id}"
            
        except ImportError as e:
            raise ImportError(
                "Google Cloud libraries not installed. "
                "Install with: pip install google-cloud-logging google-cloud-monitoring"
            ) from e
    
    def log_agent_start(self, execution: AgentExecution):
        """Log agent start to Cloud Logging."""
        self.logger.log_struct(
            {
                'severity': 'INFO',
                'agent_name': execution.agent_name,
                'output_key': execution.output_key,
                'retry_count': execution.retry_count,
                'event_type': 'agent_start',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            severity='INFO'
        )
    
    def log_agent_finish(self, execution: AgentExecution):
        """Log agent finish to Cloud Logging and send metrics to Cloud Monitoring."""
        severity = 'ERROR' if execution.status == AgentStatus.FAILED else 'INFO'
        
        # Log to Cloud Logging
        log_data = {
            'severity': severity,
            'agent_name': execution.agent_name,
            'duration_seconds': execution.duration_seconds,
            'status': execution.status.value,
            'retry_count': execution.retry_count,
            'has_output': execution.has_output,
            'event_type': 'agent_finish',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        if execution.error_message:
            log_data['error_message'] = execution.error_message
        
        self.logger.log_struct(log_data, severity=severity)
        
        # Send custom metrics to Cloud Monitoring
        self._send_agent_metrics(execution)
    
    def _send_agent_metrics(self, execution: AgentExecution):
        """Send agent execution metrics to Cloud Monitoring."""
        try:
            series = self.TimeSeries()
            series.metric.type = f"custom.googleapis.com/presentation_agent/agent_duration"
            series.resource.type = "global"
            
            # Add labels
            series.metric.labels['agent_name'] = execution.agent_name
            series.metric.labels['status'] = execution.status.value
            
            # Create data point
            from google.protobuf.timestamp_pb2 import Timestamp
            now = Timestamp()
            now.GetCurrentTime()
            
            point = self.monitoring_v3.types.Point()
            point.value.double_value = execution.duration_seconds or 0.0
            point.interval.end_time.CopyFrom(now)
            
            series.points = [point]
            
            # Write time series
            self.monitoring_client.create_time_series(
                name=self.project_name,
                time_series=[series]
            )
        except Exception as e:
            # Don't fail the pipeline if metrics fail
            print(f"⚠️  Warning: Failed to send metrics to Cloud Monitoring: {e}")
    
    def log_retry(self, agent_name: str, attempt: int, reason: str):
        """Log retry to Cloud Logging."""
        self.logger.log_struct(
            {
                'severity': 'WARNING',
                'agent_name': agent_name,
                'attempt': attempt,
                'reason': reason,
                'event_type': 'agent_retry',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            severity='WARNING'
        )
    
    def log_pipeline_start(self, pipeline_name: str):
        """Log pipeline start to Cloud Logging."""
        self.logger.log_struct(
            {
                'severity': 'INFO',
                'pipeline_name': pipeline_name,
                'event_type': 'pipeline_start',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            severity='INFO'
        )
    
    def log_pipeline_finish(self, metrics: PipelineMetrics):
        """Log pipeline finish to Cloud Logging and send metrics to Cloud Monitoring."""
        # Log to Cloud Logging
        self.logger.log_struct(
            {
                'severity': 'INFO',
                'total_duration_seconds': metrics.total_duration_seconds,
                'total_agents_executed': metrics.total_agents_executed,
                'successful_agents': metrics.successful_agents,
                'failed_agents': metrics.failed_agents,
                'total_retries': metrics.total_retries,
                'success_rate': metrics.get_success_rate(),
                'event_type': 'pipeline_finish',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            severity='INFO'
        )
        
        # Send pipeline metrics to Cloud Monitoring
        self._send_pipeline_metrics(metrics)
    
    def _send_pipeline_metrics(self, metrics: PipelineMetrics):
        """Send pipeline-level metrics to Cloud Monitoring."""
        try:
            from google.protobuf.timestamp_pb2 import Timestamp
            now = Timestamp()
            now.GetCurrentTime()
            
            series_list = []
            
            # Success rate metric
            success_rate_series = self.TimeSeries()
            success_rate_series.metric.type = "custom.googleapis.com/presentation_agent/pipeline_success_rate"
            success_rate_series.resource.type = "global"
            point = self.monitoring_v3.types.Point()
            point.value.double_value = metrics.get_success_rate()
            point.interval.end_time.CopyFrom(now)
            success_rate_series.points = [point]
            series_list.append(success_rate_series)
            
            # Duration metric
            duration_series = self.TimeSeries()
            duration_series.metric.type = "custom.googleapis.com/presentation_agent/pipeline_duration"
            duration_series.resource.type = "global"
            point = self.monitoring_v3.types.Point()
            point.value.double_value = metrics.total_duration_seconds or 0.0
            point.interval.end_time.CopyFrom(now)
            duration_series.points = [point]
            series_list.append(duration_series)
            
            # Total agents metric
            agents_series = self.TimeSeries()
            agents_series.metric.type = "custom.googleapis.com/presentation_agent/total_agents"
            agents_series.resource.type = "global"
            point = self.monitoring_v3.types.Point()
            point.value.int64_value = metrics.total_agents_executed
            point.interval.end_time.CopyFrom(now)
            agents_series.points = [point]
            series_list.append(agents_series)
            
            # Write all time series
            if series_list:
                self.monitoring_client.create_time_series(
                    name=self.project_name,
                    time_series=series_list
                )
        except Exception as e:
            # Don't fail the pipeline if metrics fail
            print(f"⚠️  Warning: Failed to send pipeline metrics to Cloud Monitoring: {e}")
    
    def save_trace_history(self, metrics: PipelineMetrics, trace_file: str):
        """Save trace history to Cloud Storage or local file as fallback."""
        # For now, also save locally as backup
        # In production, you might want to save to Cloud Storage
        from pathlib import Path
        
        trace_data = {
            'pipeline_metrics': metrics.to_dict(),
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'project_id': self.project_id
        }
        
        trace_path = Path(trace_file)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(trace_path, 'w') as f:
            json.dump(trace_data, f, indent=2, default=str)
        
        # Optionally, upload to Cloud Storage here
        # from google.cloud import storage
        # storage_client = storage.Client(project=self.project_id)
        # bucket = storage_client.bucket('your-bucket-name')
        # blob = bucket.blob(f'traces/{trace_path.name}')
        # blob.upload_from_filename(str(trace_path))


def get_observability_backend(backend_type: Optional[str] = None) -> ObservabilityBackend:
    """
    Get the appropriate observability backend based on environment.
    
    Args:
        backend_type: Backend type ('file', 'gcp', or None for auto-detect)
        
    Returns:
        ObservabilityBackend instance
    """
    # Auto-detect if not specified
    if backend_type is None:
        # Check if running on Google Cloud (Cloud Run, GCE, etc.)
        if os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT'):
            # Check if Cloud Monitoring libraries are available
            try:
                import google.cloud.logging
                import google.cloud.monitoring_v3
                backend_type = 'gcp'
            except ImportError:
                backend_type = 'file'
        else:
            backend_type = 'file'
    
    # Create backend
    if backend_type == 'gcp':
        return GoogleCloudBackend()
    elif backend_type == 'file':
        return FileBackend()
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")

