# Django Quickwit Log

A comprehensive Django package for integrating Quickwit with JSON log management and MinIO storage. This package provides seamless integration between Django applications and Quickwit for efficient log indexing and searching.

## Features

- **Django Integration**: Easy setup with Django projects
- **JSON Log Handling**: Automatic processing of JSON logs from Django's logs folder
- **Quickwit Integration**: Create and manage indexes in Quickwit
- **MinIO Storage**: Store log files in MinIO object storage (S3-compatible)
- **Docker Compose**: Ready-to-use Docker Compose configuration
- **Index Management**: Utilities for creating and managing log indexes
- **Unified Logging**: Send custom log data immediately to Quickwit
- **File Upload**: Upload existing log files to MinIO for Quickwit to read from
- **Structlog Integration**: Optional integration with existing structlog setups

## 📦 Installation

```bash 
  pip install git+[git_url]@[version]
```

## ⚙️ Configuration

Add to your Django `settings.py`:
### Installed apps

```python
INSTALLED_APPS = [
    # ... other apps
    'django_quickwit_log',
]
```
### Quickwit configuration
```python
QUICKWIT_CONFIG = {
    'url': 'quickwit-url',              # Default is: http://quickwit:7280
    'index_prefix': 'logs',             # Default is: logs
    'app_name': 'django',               # Default is: django
    'logs_dir': 'your-logs-dir-path',   # Default is: Path(getattr(settings, "BASE_DIR", "")) / 'logs')
    'enable_quickwit_indexing': True,   # Enable/disable Quickwit sending, default is True
    'enable_minio_uploads': True,       # Enable/disable MinIO uploads, default is False
    'batch_size': 100,                  # Number of logs to send in a batch
    'flush_interval': 30,               # Interval to flush logs in seconds
    'default_index_config': {},         # Default config for creating indexes
    'minio': {
        'endpoint_url': 'minio',        # Default is: minio
        'endpoint_port': '9000',        # Default is: 9000
        'access_key': 'your-access-key',
        'secret_key': 'your-secret-key',
        'bucket_name': 'your-bucket-name',
        'secure': False                 # Default is: False
    }
}
```

### Logging configuration
```python

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        # Other handlers
        # ...
        # Add Quickwit handler
        "quickwit": {
            "level": "INFO",
            "class": "django_quickwit_log.handlers.QuickwitHandler",
            "formatter": "quickwit_formatter",
            "app_name": "django",
            "batch_size": 100,
            "flush_interval": 30,
        },
    },
    'formatters': {
        # Other formatters
        # ...
        # Add Quickwit formatter
        "quickwit_formatter": {
            "()": "django_quickwit_log.handlers.JSONFormatter",
            "app_name": "django",
        },
    },
    'loggers': {
        "django_structlog": {
            "handlers": ["json_file", "quickwit"],  # Add quickwit handler
            "level": "INFO",
            "propagate": False,
        },
        "json_logger": {
            "handlers": ["json_file", "quickwit"],  # Add quickwit handler
            "level": "INFO",
            "propagate": False,
        },
    },
}
```

### Docker configuration
- Add your quickwit yaml file config in `BASE_DIR/quickwit_config/` folder
- Add quickwit docker compose service:
```bash

quickwit:
  image: quickwit/quickwit:latest
  container_name: quickwit-server
  ports:
    - "7280:7280"
  environment:
    - QW_CONFIG=./config/quickwit.yaml
  volumes:
    - quickwit_data:/quickwit/data
    - ./quickwit_config:/quickwit/config
  command: [ "run" ]
  env_file:
    - .env
```

## 📝 Usage

### 1. QuickwitLogger

The `QuickwitLogger` handles all types of logging - structlog, JSON, plain text, or any other format:

```python
from django_quickwit_log.utils import QuickwitLogger

# Create logger
logger = QuickwitLogger(app_name="myapp")

# Send dictionary logs
logger.send_log({
    "level": "ERROR",
    "message": "Database connection failed",
    "user_id": "123",
    "error_code": "DB001"
})

# Send JSON string logs
logger.send_log('{"level": "WARNING", "message": "Slow query", "query_time": 2.5}')

# Send mixed batch (dictionaries + JSON strings)
logger.send_logs_batch([
    {"level": "INFO", "message": "User logged in", "user_id": "123"},
    '{"level": "ERROR", "message": "Auth failed", "user_id": "456"}'
])

# Upload existing log files to MinIO
result = logger.upload_logs_to_minio()
print(f"Uploaded {result['files_uploaded']} files to MinIO")

# Get statistics
stats = logger.get_stats()
```

### 2. Convenience Functions

For quick operations without creating a logger instance:

```python
from django_quickwit_log.utils import send_log, send_logs_batch, upload_logs_to_minio

# Quick functions
send_log({"level": "ERROR", "message": "Test"})
send_logs_batch([{"level": "INFO", "message": "Test"}])
upload_logs_to_minio()
```

### 3. File Operations

Parse and sync existing log files:

```python
from django_quickwit_log.utils import QuickwitLogger

logger = QuickwitLogger()

# you can set app_name in QuickwitLogger init to interact with a required app index
another_app_logger = QuickwitLogger(app_name="another_app")

# Parse any log file (auto-detects format)
logs = logger.parse_log_file("logs/django.log")

# Sync specific file to Quickwit
result = logger.sync_log_file("logs/error.log")
print(f"Synced {result['logs_sent']} logs")
```

### 4. Structlog Integration (Optional)

If you want to integrate with your existing structlog setup:

```python
import structlog
from django_quickwit_log.utils.structlog_quickwit_processor import add_quickwit_processor

# Add the processor to your structlog configuration
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_quickwit_processor(app_name="myapp"),   # Add this processor
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Now you can control which logs go to Quickwit
logger = structlog.get_logger("json_logger")

# This goes to Quickwit
logger.error(
    "Critical error",
    send_to_quickwit=True,  # Add this flag
    user_id="123"
)

# This doesn't go to Quickwit
logger.info("Regular info message")
```
**Consider**: If you don't set `app_name` in processor method, configs app_name will be set as default.

##  Management Commands

### Basic Commands

```bash
# Create indexes
python manage.py quickwit_create_indexes
```
**Arguments:**
- `--app-name` Specific app name to create index for (default: all apps)
- `--force` Force recreate existing indexes
- `--dry-run` Show what would be created without actually creating

```bash
# Check Quickwit connection
python manage.py quickwit_health_check
```
**Arguments:**
- `--quickwit-only` Only check Quickwit health
- `--minio-only` Only check MinIO health
- `--verbose` Show detailed information

### QuickwitLogger Commands

```bash
# Upload all existing logs to MinIO
python manage.py quickwit_sync

# Dry run to see what would be uploaded
python manage.py quickwit_sync --dry-run

# Send a single custom log
python manage.py quickwit_sync --send-custom-log '{"level":"ERROR","message":"Test error"}'

# Send custom logs from a JSON file
python manage.py quickwit_sync --send-custom-logs-file /path/to/logs.json

# Sync a specific log file to Quickwit
python manage.py quickwit_sync --sync-log-file logs/error.log

# Parse and display a log file
python manage.py quickwit_sync --parse-log-file logs/django.log

# Show statistics
python manage.py quickwit_sync --stats
```
**Arguments:**
- `--app-name` Specific app name to sync logs for (default: config app_name)
- `--logs-dir` Path to logs directory (default: project logs folder)
- `--dry-run` Show what would be synced without actually syncing
- `--send-custom-log` Send a custom log entry (JSON string)
- `--send-custom-logs-file` Send custom logs from a JSON file
- `--sync-log-file` Sync a specific log file to Quickwit
- `--parse-log-file` Parse and display a log file
- `--stats` Show statistics about logs and integration status

##  API Reference

### QuickwitLogger Class

#### `__init__(app_name=None)`
Initialize the QuickwitLogger.

**Parameters:**
- `app_name` (str, optional): Django app name (defaults to config)

The `app_name` parameter serves as a logical identifier for organizing and categorizing logs within the Quickwit search engine. Here are its key uses:
1. **Index Naming and Organization:**
Primary Purpose: Creates unique index names in Quickwit using the pattern {index_prefix}_{app_name}
Example: If index_prefix is "logs" and app_name is "django", the index becomes logs_django
2. **Log Entry Enrichment:**
Metadata Addition: Automatically adds app_name as a field to all log entries sent to Quickwit
Purpose: Allows filtering and searching logs by application in Quickwit
Implementation
3. **Multi-Application Support:**
Flexibility: Different parts of your Django project can use different app_name values

**Example:**
```python
# Main Django app logs
logger = QuickwitLogger(app_name="django")

# specific logs  
api_logger = QuickwitLogger(app_name="payment")

# Background task logs
task_logger = QuickwitLogger(app_name="celery")
```

#### `send_log(log_data, commit='auto')`
Send a single log entry to Quickwit immediately. Accepts both dictionaries and JSON strings.

**Parameters:**
- `log_data` (dict or str): Log data dictionary or JSON string
- `commit` (str): Commit behavior ('auto' or 'force')

**Returns:** `bool` - True if sent successfully

#### `send_logs_batch(logs_data, commit='auto')`
Send multiple log entries to Quickwit in a batch. Accepts mixed dictionaries and JSON strings.

**Parameters:**
- `logs_data` (list): List of log data dictionaries or JSON strings
- `commit` (str): Commit behavior ('auto' or 'force')

**Returns:** `bool` - True if sent successfully

#### `upload_logs_to_minio(logs_dir=None)`
Upload existing log files to MinIO storage for Quickwit to read from.

**Parameters:**
- `logs_dir` (str, optional): Path to logs directory

**Returns:** `dict` - Dictionary with upload results

#### `parse_log_file(file_path)`
Parse a log file and return structured log entries. Auto-detects format.

**Parameters:**
- `file_path` (str): Path to the log file

**Returns:** `list` - List of parsed log entries

#### `sync_log_file(file_path, commit='auto')`
Parse and sync a single log file to Quickwit.

**Parameters:**
- `file_path` (str): Path to the log file
- `commit` (str): Commit behavior ('auto' or 'force')

**Returns:** `dict` - Dictionary with sync results

#### `get_stats()`
Get statistics about logs and integration status.

**Returns:** `dict` - Dictionary with statistics

### Convenience Functions

```python
from django_quickwit_log.utils import (
    send_log,
    send_logs_batch,
    upload_logs_to_minio,
    get_stats,
    parse_log_file,
    sync_log_file,
)

# Convenience wrappers
send_log({"level": "ERROR", "message": "Test"})
send_logs_batch([{"level": "INFO", "message": "Test"}])
upload_logs_to_minio()
get_stats()
parse_log_file("logs/django.log")
sync_log_file("logs/error.log")
```

## QuickwitClient

Main client for interacting with Quickwit:

**Examples:**
```python
from django_quickwit_log.client.quickwit_client import QuickwitClient

client = QuickwitClient()

# Check if Quickwit server is healthy
client.health_check()

# List all available indexes
client.list_indexes()

# Create a new index
client.create_index(index_config=index_config)

# Delete an index
client.delete_index(index_id='my_index')

# Clears documents of index id.
client.clear_index(index_id='my_index')

# The response is the stats about the requested index.
client.get_index_stats(index_id='my_index')

# Index a batch of documents into an index using NDJSON payload.
client.index_documents(index_id='my_index', documents=documents, commit="force")

# Index a single document into an index.
client.index_document(index_id='my_index', document=document, commit="auto")

# Search documents in an index.
client.search(index_id='my_index', query='level:ERROR')
```
query language doc: https://quickwit.io/docs/reference/query-language

## MinIOStorage

Storage client for MinIO:

```python
from django_quickwit_log.storage.minio_storage import MinIOStorage

storage = MinIOStorage()
storage.health_check()
storage.upload_file('logs/app.log', 'app.log')
storage.sync_logs_directory('my_app', './logs')
storage.upload_log_file('my_app', './logs')
```

##  Advanced Usage

### Custom Log Processing

```python
def process_logs_with_filter():
    """Process logs with custom filtering."""
    from django_quickwit_log.utils import QuickwitLogger
    logger = QuickwitLogger()
    
    # Parse a specific log file
    logs = logger.parse_log_file("logs/django.log")
    
    # Filter logs by level
    error_logs = [log for log in logs if log.get('level') == 'ERROR']
    
    # Send filtered logs to Quickwit
    if error_logs:
        logger.send_logs_batch(error_logs)
```

### Statistics and Monitoring

```python
def monitor_logs():
    """Monitor log statistics."""
    from django_quickwit_log.utils import QuickwitLogger
    stats = QuickwitLogger().get_stats()
    
    print(f"App: {stats['app_name']}")
    print(f"Log Files: {stats['log_files_count']}")
    print(f"Quickwit Enabled: {stats['quickwit_enabled']}")
    print(f"MinIO Enabled: {stats['minio_enabled']}")
    
    if stats.get('index_stats'):
        print(f"Index Stats: {stats['index_stats']}")
```

### Health Checks

```python
from django_quickwit_log.client import QuickwitClient
from django_quickwit_log.storage import MinIOStorage

# Check Quickwit connection (tries health endpoints)
quickwit_client = QuickwitClient()
print("Quickwit healthy:", quickwit_client.health_check())

# Check MinIO connection
storage_client = MinIOStorage()
if storage_client.health_check():
    print("✓ MinIO is healthy")
else:
    print("✗ MinIO connection failed")
```

## 🐛 Troubleshooting

### Common Issues

1. **Connection Error**: Check if Quickwit server is running
2. **Index Not Found**: The index will be created automatically
3. **MinIO Upload Failed**: Check MinIO credentials and bucket permissions
4. **JSON Parse Error**: Ensure log files contain valid JSON
5. **Timestamp Format Error**: Use UTC-Z format: `2024-01-15T10:30:00Z`


## 🤝 Contributing

1. Fork the repositor