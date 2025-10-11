import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from ..client import QuickwitClient
from ..storage import MinIOStorage
from django_quickwit_log.config import get_quickwit_config
from ..utils.log_processor import LogProcessor


class QuickwitHandler(logging.Handler):
    """
    Django logging handler that sends logs to Quickwit.
    
    This handler processes log records, formats them as JSON,
    and sends them to Quickwit for indexing. It also handles
    file-based logging and MinIO storage integration.
    """

    def __init__(self,
                 app_name: str = None,
                 batch_size: int = 100,
                 flush_interval: int = 30,
                 **kwargs):
        """
        Initialize Quickwit handler.
        
        Args:
            app_name: Django app name
            batch_size: Number of logs to batch before sending
            flush_interval: Seconds between automatic flushes
            **kwargs: Additional handler arguments
        """
        super().__init__(**kwargs)

        self.config = get_quickwit_config()
        self.app_name = app_name or self.config.get('app_name')
        self.index_id = f"{self.config.get('index_prefix')}_{self.app_name}"
        self.batch_size = batch_size or self.config.get('batch_size')
        self.flush_interval = flush_interval or self.config.get('flush_interval')

        self.quickwit_client = QuickwitClient()
        self.storage_client = MinIOStorage()
        self.log_processor = LogProcessor()

        self._log_batch: List[Dict[str, Any]] = []
        self._last_flush = datetime.now()

        self.logs_dir = self.config.get('logs_dir')
        self.logs_dir.mkdir(exist_ok=True)

        self._setup_periodic_flush()

    def _setup_periodic_flush(self) -> None:
        """Setup periodic batch flushing."""
        import threading
        import time

        def flush_worker():
            while True:
                time.sleep(self.flush_interval)
                self.flush()

        flush_thread = threading.Thread(target=flush_worker, daemon=True)
        flush_thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.
        
        Args:
            record: Log record to emit
        """
        try:
            log_data = self._record_to_dict(record)
            self._log_batch.append(log_data)
            self._write_to_file(log_data)

            # Check if we should flush the batch
            if len(self._log_batch) >= self.batch_size:
                self._flush_batch()

        except Exception as e:
            print(f"Error in QuickwitHandler.emit: {e}")

    def _record_to_dict(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Convert log record to dictionary.
        
        Args:
            record: Log record to convert
            
        Returns:
            Dictionary representation of the log record
        """
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
            'app_name': self.app_name,
        }

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in log_data and not key.startswith('_'):
                try:
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return log_data

    def _write_to_file(self, log_data: Dict[str, Any]) -> None:
        """
        Write log data to file.
        
        Args:
            log_data: Log data to write
        """
        try:
            # Create daily log file
            date_str = datetime.now().strftime('%Y-%m-%d')
            log_file = self.logs_dir / f"{self.app_name}_{date_str}.json"

            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_data, ensure_ascii=False) + '\n')

        except Exception as e:
            print(f"Error writing to log file: {e}")

    def _flush_batch(self) -> None:
        """Flush the current batch to Quickwit."""
        if not self._log_batch:
            return

        try:
            if self.config.get('enable_quickwit_indexing', True):
                self.quickwit_client.create_log_index(self.app_name)

                self.quickwit_client.index_documents(
                    self.index_id,
                    self._log_batch
                )

            self._log_batch.clear()
            self._last_flush = datetime.now()

        except Exception as e:
            print(f"Error flushing log batch: {e}")

    def flush(self) -> None:
        """Flush any pending logs."""
        self._flush_batch()
        super().flush()

    def close(self) -> None:
        """Close the handler and flush any remaining logs."""
        self.flush()
        super().close()

    def sync_logs_to_storage(self) -> List[str]:
        """
        Sync log files to MinIO storage.
        
        Returns:
            List of uploaded file URLs
        """
        try:
            if not self.config.get('enable_minio_uploads', False):
                return []
            return self.storage_client.sync_logs_directory(
                self.app_name,
                str(self.logs_dir)
            )
        except Exception as e:
            print(f"Error syncing logs to storage: {e}")
            return []

    def log_now(self, level: int, message: str, **extra_fields: Any) -> bool:
        """
        Send one log immediately to Quickwit, regardless of batching or file persistence.
        Always writes to file as well.
        """
        try:
            # Build log entry aligned with _record_to_dict keys
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'level': logging.getLevelName(level),
                'logger': self.__class__.__name__,
                'message': message,
                'module': __name__,
                'function': 'log_now',
                'line': 0,
                'thread': 0,
                'process': 0,
                'app_name': self.app_name,
                **extra_fields,
            }
            self._write_to_file(log_data)
            # Send immediately to Quickwit if enabled
            if self.config.get('enable_quickwit_indexing', True):
                self.quickwit_client.create_log_index(self.app_name)
                self.quickwit_client.index_document(self.index_id, log_data, commit='force')
            return True
        except Exception as e:
            print(f"Error in log_now: {e}")
            return False

    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get logging statistics.
        
        Returns:
            Dictionary with logging statistics
        """
        try:
            stats = self.quickwit_client.get_index_stats(self.index_id)

            return {
                'app_name': self.app_name,
                'batch_size': len(self._log_batch),
                'last_flush': self._last_flush.isoformat(),
                'index_stats': stats,
                'logs_directory': str(self.logs_dir),
            }
        except Exception as e:
            return {
                'app_name': self.app_name,
                'error': str(e),
                'batch_size': len(self._log_batch),
                'last_flush': self._last_flush.isoformat(),
            }
