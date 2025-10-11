import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Union

from django_quickwit_log.config import get_quickwit_config
from ..client import QuickwitClient
from ..storage import MinIOStorage


class QuickwitLogger:
    """
    QuickwitLogger handles all types of logging:
    - structlog entries
    - regular JSON logs
    - any other structured log format
    
    Features:
    - Send custom log data (dict) to Quickwit immediately
    - Upload existing log files to MinIO for Quickwit to read from
    - Support both single logs and batch operations
    - Auto-detect and parse different log formats
    - Works with any logging framework
    """

    def __init__(self, app_name: str = None):
        """
        Initialize the QuickwitLogger.
        
        Args:
            app_name: Django app name (defaults to config)
        """
        self.config = get_quickwit_config()
        self.app_name = app_name or self.config.get('app_name')

        self.quickwit_client = QuickwitClient()
        self.storage_client = MinIOStorage()

    def _enrich_log_entry(self, log_data: Dict[str, Any], app_name: str) -> Dict[str, Any]:
        """Enrich log entry with app name and ensure required fields."""
        enriched = log_data.copy()

        if 'app_name' not in enriched:
            enriched['app_name'] = app_name

        return enriched

    def _ensure_timestamp(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure log has proper UTC-Z timestamp."""
        if 'timestamp' not in log_data:
            log_data['timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        elif not log_data['timestamp'].endswith('Z'):
            log_data['timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return log_data

    def send_log(self, log_data: Union[Dict[str, Any], str], commit: str = 'auto') -> bool:
        """
        Send a single log entry to Quickwit immediately.
        
        Args:
            log_data: Dictionary containing log data OR JSON string
            commit: Commit behavior ('auto' or 'force')
            
        Returns:
            True if sent successfully
            
        Example:
            # With dictionary
            logger = QuickwitLogger()
            logger.send_log({
                "level": "ERROR",
                "message": "Database connection failed",
                "user_id": "123"
            })
            
            # With JSON string
            logger.send_log('{"level": "ERROR", "message": "Test"}')
        """
        try:
            if not self.config.get('enable_quickwit_indexing', True):
                return True

            # Parse JSON string if needed
            if isinstance(log_data, str):
                try:
                    log_data = json.loads(log_data)
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON in log_data: {e}")
                    return False

            # Ensure timestamp is in UTC-Z format
            log_data = self._ensure_timestamp(log_data)

            # Enrich log with app name
            enriched_log = self._enrich_log_entry(log_data, self.app_name)

            # Create index if needed
            self.quickwit_client.create_log_index(self.app_name)

            # Send to Quickwit
            index_id = f"{self.config.get('index_prefix')}_{self.app_name}"
            return self.quickwit_client.index_document(index_id, enriched_log, commit=commit)

        except Exception as e:
            logging.error(f"Error sending log to Quickwit: {e}")
            return False

    def send_logs_batch(self, logs_data: List[Union[Dict[str, Any], str]], commit: str = 'auto') -> bool:
        """
        Send multiple log entries to Quickwit in a batch.
        
        Args:
            logs_data: List of log data dictionaries or JSON strings
            commit: Commit behavior ('auto' or 'force')
            
        Returns:
            True if sent successfully
            
        Example:
            logger = QuickwitLogger()
            logs = [
                {"level": "INFO", "message": "User logged in", "user_id": "123"},
                '{"level": "WARNING", "message": "Slow query", "query_time": 2.5}'
            ]
            logger.send_logs_batch(logs)
        """
        try:
            if not self.config.get('enable_quickwit_indexing', True):
                return True

            if not logs_data:
                return True

            # Parse and process all logs
            processed_logs = []
            for log_data in logs_data:
                # Parse JSON string if needed
                if isinstance(log_data, str):
                    try:
                        log_data = json.loads(log_data)
                    except json.JSONDecodeError as e:
                        logging.error(f"Invalid JSON in logs_data: {e}")
                        continue

                # Ensure timestamp is in UTC-Z format
                log_data = self._ensure_timestamp(log_data)
                processed_logs.append(log_data)

            if not processed_logs:
                return False

            # Enrich logs with app name
            enriched_logs = [
                self._enrich_log_entry(log_data, self.app_name)
                for log_data in processed_logs
            ]

            # Create index if needed
            self.quickwit_client.create_log_index(self.app_name)

            # Send to Quickwit
            index_id = f"{self.config.get('index_prefix')}_{self.app_name}"
            return self.quickwit_client.index_documents(index_id, enriched_logs, commit=commit)

        except Exception as e:
            logging.error(f"Error sending logs batch to Quickwit: {e}")
            return False

    def upload_logs_to_minio(self, logs_dir: str = None) -> Dict[str, Any]:
        """
        Upload existing log files to MinIO storage for Quickwit to read from.
        
        Args:
            logs_dir: Path to logs directory (defaults to project logs folder)
            
        Returns:
            Dictionary with upload results
            
        Example:
            logger = QuickwitLogger()
            result = logger.upload_logs_to_minio()
            print(f"Uploaded {result['files_uploaded']} files")
        """
        try:
            if not self.config.get('enable_minio_uploads', True):
                return {
                    'success': True,
                    'files_processed': 0,
                    'files_uploaded': 0,
                    'message': 'MinIO uploads disabled in config'
                }

            target_logs_dir = logs_dir or str(self.config.get("logs_dir"))
            logs_path = Path(target_logs_dir)

            if not logs_path.exists():
                return {
                    'success': False,
                    'error': f'Logs directory does not exist: {target_logs_dir}',
                    'files_processed': 0,
                    'files_uploaded': 0
                }

            # Find all log files
            log_files = list(logs_path.glob('*.json')) + list(logs_path.glob('*.log'))

            if not log_files:
                return {
                    'success': True,
                    'files_processed': 0,
                    'files_uploaded': 0,
                    'message': 'No log files found'
                }

            uploaded_urls = []
            files_uploaded = 0

            for log_file in log_files:
                try:
                    url = self.storage_client.upload_log_file(self.app_name, str(log_file))
                    uploaded_urls.append(url)
                    files_uploaded += 1
                except Exception as e:
                    logging.error(f"Failed to upload {log_file.name}: {e}")

            return {
                'success': True,
                'files_processed': len(log_files),
                'files_uploaded': files_uploaded,
                'uploaded_urls': uploaded_urls
            }

        except Exception as e:
            logging.error(f"Error uploading logs to MinIO: {e}")
            return {
                'success': False,
                'error': str(e),
                'files_processed': 0,
                'files_uploaded': 0
            }

    def parse_log_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse a log file and return structured log entries.
        Auto-detects format (JSON lines, single JSON, etc.)
        
        Args:
            file_path: Path to the log file
            
        Returns:
            List of parsed log entries
        """
        try:
            logs = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # Try to parse as JSON
                        log_entry = json.loads(line)
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # If not JSON, create a structured entry from the line
                        logs.append({
                            'message': line,
                            'line_number': line_num,
                            'file': file_path,
                            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                        })

            return logs

        except Exception as e:
            logging.error(f"Error parsing log file {file_path}: {e}")
            return []

    def sync_log_file(self, file_path: str, commit: str = 'auto') -> Dict[str, Any]:
        """
        Parse and sync a single log file to Quickwit.
        
        Args:
            file_path: Path to the log file
            commit: Commit behavior ('auto' or 'force')
            
        Returns:
            Dictionary with sync results
        """
        try:
            logs = self.parse_log_file(file_path)
            if not logs:
                return {
                    'success': True,
                    'logs_processed': 0,
                    'message': 'No valid log entries found'
                }

            # Send logs in batches
            batch_size = 100
            total_sent = 0

            for i in range(0, len(logs), batch_size):
                batch = logs[i:i + batch_size]
                if self.send_logs_batch(batch, commit):
                    total_sent += len(batch)

            return {
                'success': True,
                'logs_processed': len(logs),
                'logs_sent': total_sent
            }

        except Exception as e:
            logging.error(f"Error syncing log file {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'logs_processed': 0,
                'logs_sent': 0
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about logs and integration status.
        
        Returns:
            Dictionary with statistics
        """
        try:
            stats = {
                'app_name': self.app_name,
                'logs_directory': str(self.config.get("logs_dir")),
                'log_files_count': 0,
                'quickwit_enabled': self.config.get('enable_quickwit_indexing', True),
                'minio_enabled': self.config.get('enable_minio_uploads', True),
            }

            if self.config.get("logs_dir") and Path(self.config.get("logs_dir")).exists():
                log_files = list(Path(self.config.get("logs_dir")).glob('*.json')) + list(
                    Path(self.config.get("logs_dir")).glob('*.log'))
                stats['log_files_count'] = len(log_files)

            if stats['quickwit_enabled']:
                try:
                    index_id = f"{self.config.get('index_prefix')}_{self.app_name}"
                    index_stats = self.quickwit_client.get_index_stats(index_id)
                    stats['index_stats'] = index_stats
                except Exception as e:
                    stats['error'] = f"Could not get index stats: {e}"

            return stats

        except Exception as e:
            return {
                'app_name': self.app_name,
                'error': str(e),
                'quickwit_enabled': False,
                'minio_enabled': False
            }


def send_log(log_data: Union[Dict[str, Any], str], app_name: str = None) -> bool:
    """Convenience function to send a single log."""
    logger = QuickwitLogger(app_name)
    return logger.send_log(log_data)


def send_logs_batch(logs_data: List[Union[Dict[str, Any], str]], app_name: str = None) -> bool:
    """Convenience function to send multiple logs."""
    logger = QuickwitLogger(app_name)
    return logger.send_logs_batch(logs_data)


def upload_logs_to_minio(app_name: str = None, logs_dir: str = None) -> Dict[str, Any]:
    """Convenience function to upload logs to MinIO."""
    logger = QuickwitLogger(app_name)
    return logger.upload_logs_to_minio(logs_dir)


def get_stats(app_name: str = None) -> Dict[str, Any]:
    """Convenience function to get statistics."""
    logger = QuickwitLogger(app_name)
    return logger.get_stats()


def parse_log_file(file_path: str) -> List[Dict[str, Any]]:
    """Convenience function to parse a log file."""
    logger = QuickwitLogger()
    return logger.parse_log_file(file_path)


def sync_log_file(file_path: str, app_name: str = None) -> Dict[str, Any]:
    """Convenience function to sync a log file to Quickwit."""
    logger = QuickwitLogger(app_name)
    return logger.sync_log_file(file_path)
