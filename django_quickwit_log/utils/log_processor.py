import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator

logger = logging.getLogger(__name__)


class LogProcessor:
    """
    Utility class for processing log files and data.
    
    This class provides methods for reading, parsing, and processing
    log files in various formats.
    """

    def __init__(self):
        pass

    def read_json_logs(self, file_path: str) -> Iterator[Dict[str, Any]]:
        """
        Read JSON log entries from a file.
        
        Args:
            file_path: Path to the log file
            
        Yields:
            Dictionary containing log entry data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        log_entry = json.loads(line)
                        yield log_entry
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in {file_path} line {line_num}: {e}")
                        continue

        except FileNotFoundError:
            logger.error(f"Log file not found: {file_path}")
        except Exception as e:
            logger.error(f"Error reading log file {file_path}: {e}")

    def process_log_directory(self, directory: str,
                              file_pattern: str = "*.json") -> Iterator[Dict[str, Any]]:
        """
        Process all log files in a directory.
        
        Args:
            directory: Path to the log directory
            file_pattern: File pattern to match (e.g., "*.json", "*.log")
            
        Yields:
            Dictionary containing log entry data
        """
        log_dir = Path(directory)

        if not log_dir.exists():
            logger.warning(f"Log directory does not exist: {directory}")
            return

        for log_file in log_dir.glob(file_pattern):
            logger.info(f"Processing log file: {log_file}")

            if log_file.suffix == '.json':
                yield from self.read_json_logs(str(log_file))
            else:
                # For non json files, try to parse as json lines
                yield from self.read_json_logs(str(log_file))

    def parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line.
        
        Args:
            line: Log line to parse
            
        Returns:
            Parsed log entry or None if parsing fails
        """
        line = line.strip()
        if not line:
            return None

        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return self._parse_simple_log_line(line)

    def _parse_simple_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a simple log line format.
        
        Args:
            line: Log line to parse
            
        Returns:
            Parsed log entry or None if parsing fails
        """
        # Simple format: timestamp level message
        parts = line.split(' ', 2)
        if len(parts) < 3:
            return None

        try:
            timestamp_str, level, message = parts
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

            return {
                'timestamp': timestamp.isoformat(),
                'level': level,
                'message': message,
                'raw_line': line,
            }
        except ValueError:
            return None

    def validate_log_entry(self, log_entry: Dict[str, Any]) -> bool:
        """
        Validate a log entry.
        
        Args:
            log_entry: Log entry to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['timestamp', 'level', 'message']

        for field in required_fields:
            if field not in log_entry:
                logger.warning(f"Missing required field '{field}' in log entry")
                return False

        try:
            datetime.fromisoformat(log_entry['timestamp'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp format: {log_entry['timestamp']}")
            return False

        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_entry['level'] not in valid_levels:
            logger.warning(f"Invalid log level: {log_entry['level']}")
            return False

        return True

    def enrich_log_entry(self, log_entry: Dict[str, Any],
                         app_name: str = None) -> Dict[str, Any]:
        """
        Enrich a log entry with additional metadata.
        
        Args:
            log_entry: Log entry to enrich
            app_name: Application name to add
            
        Returns:
            Enriched log entry
        """
        enriched = log_entry.copy()

        if app_name:
            enriched['app_name'] = app_name

        enriched['processed_at'] = datetime.now().isoformat()

        if 'source' not in enriched:
            enriched['source'] = 'django_quickwit_log'

        return enriched

    def batch_logs(self, logs: Iterator[Dict[str, Any]],
                   batch_size: int = 100) -> Iterator[List[Dict[str, Any]]]:
        """
        Batch log entries for processing.
        
        Args:
            logs: Iterator of log entries
            batch_size: Size of each batch
            
        Yields:
            List of log entries in each batch
        """
        batch = []

        for log_entry in logs:
            batch.append(log_entry)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def get_log_statistics(self, logs: Iterator[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get statistics about log entries.
        
        Args:
            logs: Iterator of log entries
            
        Returns:
            Dictionary with log statistics
        """
        stats = {
            'total_entries': 0,
            'level_counts': {},
            'app_counts': {},
            'date_range': {'earliest': None, 'latest': None},
            'error_count': 0,
        }

        for log_entry in logs:
            stats['total_entries'] += 1

            level = log_entry.get('level', 'UNKNOWN')
            stats['level_counts'][level] = stats['level_counts'].get(level, 0) + 1

            app_name = log_entry.get('app_name', 'unknown')
            stats['app_counts'][app_name] = stats['app_counts'].get(app_name, 0) + 1

            if level in ['ERROR', 'CRITICAL']:
                stats['error_count'] += 1

            timestamp = log_entry.get('timestamp')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if stats['date_range']['earliest'] is None or dt < stats['date_range']['earliest']:
                        stats['date_range']['earliest'] = dt
                    if stats['date_range']['latest'] is None or dt > stats['date_range']['latest']:
                        stats['date_range']['latest'] = dt
                except ValueError:
                    pass

        if stats['date_range']['earliest']:
            stats['date_range']['earliest'] = stats['date_range']['earliest'].isoformat()
        if stats['date_range']['latest']:
            stats['date_range']['latest'] = stats['date_range']['latest'].isoformat()

        return stats
