"""Retry event logger for tracking blocking detection and recovery.

This module provides session-based JSON logging for all retry events during scraping.
Each session gets a unique timestamped log file with detailed event information including
retry metadata, block types, and degradation status.

Key Features:
    - Session-based logging with YYYYMMDD_HHMMSS format
    - JSON-structured event data for easy parsing
    - Retry statistics and session summaries
    - Degradation event tracking
    - Singleton instance for consistent session tracking

Log Structure:
    {
      "session_id": "20260105_150717",
      "events": [
        {
          "timestamp": "2026-01-05T15:07:17.123456",
          "url": "https://example.com",
          "error_type": "RequestException",
          "retry_metadata": {...},
          "outcome": "retry_scheduled"
        }
      ],
      "degradation_info": {
        "is_degraded": false,
        "degradation_timestamp": null
      }
    }

Typical Usage:
    from src.retry_logger import retry_logger
    
    # Log retry event
    retry_logger.log_retry_event(event)
    
    # Get session summary
    summary = retry_logger.get_session_summary()
    
    # Log degradation
    retry_logger.log_degradation("3 consecutive failures")
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from src.models import RetryEvent


class RetryLogger:
    """Session-based logger for retry events."""
    
    def __init__(self, output_dir: str = "Output"):
        """Initialize retry logger with session ID.
        
        Args:
            output_dir: Base output directory (default: "Output")
        """
        self.output_dir = Path(output_dir)
        self.log_dir = self.output_dir / "retry_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate session ID with YYYYMMDD_HHMMSS format
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{self.session_id}_retry_log.json"
        
        # Initialize log structure
        self._log_data = {
            "session_id": self.session_id,
            "events": [],
            "degradation_info": {
                "is_degraded": False,
                "degradation_timestamp": None,
                "degradation_reason": None
            }
        }
        
        # Write initial log file
        self._write_log()
    
    def log_retry_event(self, event: RetryEvent) -> None:
        """Log a retry event to the session log file.
        
        Args:
            event: RetryEvent object to log
        """
        # Convert Pydantic model to dict
        event_dict = event.model_dump(exclude_none=False)
        
        # Add to events list
        self._log_data["events"].append(event_dict)
        
        # Write updated log
        self._write_log()
    
    def _write_log(self) -> None:
        """Write current log data to JSON file."""
        with open(self.log_file, 'w') as f:
            json.dump(self._log_data, f, indent=2)
    
    def get_session_summary(self) -> Dict:
        """Get statistics summary for the current session.
        
        Returns:
            Dictionary with retry statistics
        """
        events = self._log_data["events"]
        
        if not events:
            return {
                "total_retries": 0,
                "success_count": 0,
                "failure_count": 0,
                "avg_wait_time": 0.0,
                "total_cumulative_wait": 0.0
            }
        
        # Calculate statistics
        total_retries = len(events)
        success_count = sum(1 for e in events if e.get("outcome") == "success")
        failure_count = sum(1 for e in events if e.get("outcome") == "permanent_failure")
        
        # Calculate wait time statistics
        wait_times = [
            e.get("retry_metadata", {}).get("wait_time", 0.0)
            for e in events
            if e.get("retry_metadata")
        ]
        
        cumulative_waits = [
            e.get("retry_metadata", {}).get("cumulative_wait", 0.0)
            for e in events
            if e.get("retry_metadata")
        ]
        
        avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0.0
        total_cumulative_wait = max(cumulative_waits) if cumulative_waits else 0.0
        
        return {
            "total_retries": total_retries,
            "success_count": success_count,
            "failure_count": failure_count,
            "avg_wait_time": round(avg_wait_time, 2),
            "total_cumulative_wait": round(total_cumulative_wait, 2)
        }
    
    def log_degradation(self, reason: str) -> None:
        """Log that the system has entered degraded mode.
        
        Args:
            reason: Reason for entering degraded mode
        """
        self._log_data["degradation_info"] = {
            "is_degraded": True,
            "degradation_timestamp": datetime.now().isoformat(),
            "degradation_reason": reason
        }
        self._write_log()


# Create singleton instance for import in other modules
retry_logger = RetryLogger()
