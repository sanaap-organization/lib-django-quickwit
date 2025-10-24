import json
import logging
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for Django logs.
    
    This formatter converts log records to JSON format suitable for
    indexing in Quickwit.
    """

    def __init__(self, app_name: str = None, **kwargs):
        """
        Initialize JSON formatter.
        
        Args:
            app_name: Django app name to include in logs
            **kwargs: Additional formatter arguments
        """
        super().__init__(**kwargs)
        self.app_name = app_name

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation of the log record
        """
        # Extract basic information
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process,
        }

        if self.app_name:
            log_data['app_name'] = self.app_name

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in log_data and not key.startswith('_'):
                # Convert non-serializable objects to strings
                try:
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data, ensure_ascii=False)
