import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from django_quickwit_log.config import get_quickwit_config
from django_quickwit_log.utils.quickwit_logger import QuickwitLogger


class Command(BaseCommand):
    """Unified command for all logging operations."""
    
    help = 'Unified logging operations - send custom logs, upload files, sync logs'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--logs-dir',
            type=str,
            help='Path to logs directory (default: project logs folder)',
        )
        parser.add_argument(
            '--app-name',
            type=str,
            help='Specific app name to sync logs for',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing',
        )
        parser.add_argument(
            '--send-custom-log',
            type=str,
            help='Send a custom log entry (JSON string)',
        )
        parser.add_argument(
            '--send-custom-logs-file',
            type=str,
            help='Send custom logs from a JSON file',
        )
        parser.add_argument(
            '--sync-log-file',
            type=str,
            help='Sync a specific log file to Quickwit',
        )
        parser.add_argument(
            '--parse-log-file',
            type=str,
            help='Parse and display a log file',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show statistics about logs and integration status',
        )
    
    def handle(self, *args, **options):
        """Handle the command."""
        self.config = get_quickwit_config()
        try:
            app_name = options.get('app_name')
            logs_dir = options.get('logs_dir')
            dry_run = options.get('dry_run', False)
            send_custom_log = options.get('send_custom_log')
            send_custom_logs_file = options.get('send_custom_logs_file')
            sync_log_file = options.get('sync_log_file')
            parse_log_file = options.get('parse_log_file')
            stats = options.get('stats', False)

            if dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN MODE - No data will be synced')
                )

            if send_custom_log:
                self._send_custom_log(send_custom_log, app_name, dry_run)
                return

            if send_custom_logs_file:
                self._send_custom_logs_from_file(send_custom_logs_file, app_name, dry_run)
                return

            if sync_log_file:
                self._sync_log_file(sync_log_file, app_name, dry_run)
                return

            if parse_log_file:
                self._parse_log_file(parse_log_file)
                return

            if stats:
                self._show_statistics(app_name)
                return

            self._upload_existing_logs(
                app_name, logs_dir, dry_run
            )

        except Exception as e:
            raise CommandError(f'Error with unified logger operations: {e}')
    
    def _send_custom_log(self, log_json, app_name, dry_run):
        """Send a custom log entry."""
        try:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'Would send log: {log_json}')
                )
                return
            
            logger = QuickwitLogger(app_name)
            success = logger.send_log(log_json)
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS('Custom log sent to Quickwit successfully')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to send custom log to Quickwit')
                )
                
        except Exception as e:
            raise CommandError(f'Error sending custom log: {e}')
    
    def _send_custom_logs_from_file(self, file_path, app_name, dry_run):
        """Send custom logs from a JSON file."""
        try:
            with open(file_path, 'r') as f:
                logs_data = json.load(f)
            
            if not isinstance(logs_data, list):
                raise CommandError('JSON file must contain an array of log objects')
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'Would send {len(logs_data)} logs from {file_path}')
                )
                return
            
            logger = QuickwitLogger(app_name)
            success = logger.send_logs_batch(logs_data)
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Sent {len(logs_data)} custom logs to Quickwit')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Failed to send custom logs to Quickwit')
                )
                
        except FileNotFoundError:
            raise CommandError(f'File not found: {file_path}')
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON in file {file_path}: {e}')
        except Exception as e:
            raise CommandError(f'Error sending custom logs from file: {e}')
    
    def _sync_log_file(self, file_path, app_name, dry_run):
        """Sync a specific log file to Quickwit."""
        try:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'Would sync log file: {file_path}')
                )
                return
            
            logger = QuickwitLogger(app_name)
            result = logger.sync_log_file(file_path)
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Synced {result["logs_sent"]} logs from {file_path}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to sync log file: {result.get("error", "Unknown error")}')
                )
                
        except Exception as e:
            raise CommandError(f'Error syncing log file: {e}')
    
    def _parse_log_file(self, file_path):
        """Parse and display a log file."""
        try:
            logger = QuickwitLogger()
            logs = logger.parse_log_file(file_path)
            
            self.stdout.write(f'Parsed {len(logs)} log entries from {file_path}:')
            for i, log in enumerate(logs[:5]):  # Show first 5 entries
                self.stdout.write(f'  {i+1}. {json.dumps(log, indent=2)}')
            
            if len(logs) > 5:
                self.stdout.write(f'  ... and {len(logs) - 5} more entries')
                
        except Exception as e:
            raise CommandError(f'Error parsing log file: {e}')
    
    def _show_statistics(self, app_name):
        """Show statistics about logs and integration."""
        try:
            logger = QuickwitLogger(app_name)
            stats = logger.get_stats()
            
            self.stdout.write('\n' + '='*50)
            self.stdout.write('UNIFIED LOGGER STATISTICS')
            self.stdout.write('='*50)
            
            self.stdout.write(f"App Name: {stats.get('app_name', 'Unknown')}")
            self.stdout.write(f"Logs Directory: {stats.get('logs_directory', 'Unknown')}")
            self.stdout.write(f"Log Files Count: {stats.get('log_files_count', 0)}")
            self.stdout.write(f"Quickwit Enabled: {stats.get('quickwit_enabled', False)}")
            self.stdout.write(f"MinIO Enabled: {stats.get('minio_enabled', False)}")
            
            if stats.get('index_stats'):
                self.stdout.write(f"\nIndex Statistics:")
                self.stdout.write(f"  {stats['index_stats']}")
            
            if stats.get('error'):
                self.stdout.write(f"\nError: {stats['error']}")
            
            self.stdout.write('='*50)
            
        except Exception as e:
            raise CommandError(f'Error getting statistics: {e}')
    
    def _upload_existing_logs(self, app_name, logs_dir, dry_run):
        """Upload existing log files to MinIO."""
        try:
            if dry_run:
                # For dry run, just show what would be processed
                logs_path = Path(logs_dir) or self.config.get("logs_dir")
                if logs_path.exists():
                    log_files = list(logs_path.glob('*.json')) + list(logs_path.glob('*.log'))
                    self.stdout.write(f'Would upload {len(log_files)} log files to MinIO')
                else:
                    self.stdout.write(f'Logs directory does not exist: {logs_path}')
                return
            
            # Perform actual upload
            logger = QuickwitLogger(app_name)
            result = logger.upload_logs_to_minio(logs_dir)
            
            if result['success']:
                self.stdout.write('✓ Upload completed successfully')
                self.stdout.write(f'  Files processed: {result["files_processed"]}')
                self.stdout.write(f'  Files uploaded: {result["files_uploaded"]}')
                
                if result.get('uploaded_urls'):
                    self.stdout.write('  Uploaded URLs:')
                    for url in result['uploaded_urls']:
                        self.stdout.write(f'    - {url}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ Upload failed: {result.get("error", "Unknown error")}')
                )
            
        except Exception as e:
            raise CommandError(f'Error uploading existing logs: {e}')
