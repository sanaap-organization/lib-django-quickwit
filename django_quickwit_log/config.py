from pathlib import Path
from typing import Dict, Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django_quickwit_log.utils.constants import default_index_config


def get_quickwit_config() -> Dict[str, Any]:
    """
    Get Quickwit configuration from Django settings.
    
    Returns:
        Quickwit configuration dictionary
    """
    config = getattr(settings, 'QUICKWIT_CONFIG', {})
    if not config:
        raise ImproperlyConfigured("QUICKWIT_CONFIG is missing in Django settings")

    return {
        'url': config.get('url', 'http://quickwit:7280'),
        'index_prefix': config.get('index_prefix', 'logs'),
        'app_name': config.get('app_name', 'django'),
        'logs_dir': config.get('logs_dir', Path(getattr(settings, "BASE_DIR", "")) / 'logs'),
        'batch_size': config.get('batch_size', 100),
        'flush_interval': config.get('flush_interval', 30),
        'enable_quickwit_indexing': config.get('enable_quickwit_indexing', True),
        'enable_minio_uploads': config.get('enable_minio_uploads', False),
        "default_index_config": config.get('default_index_config', default_index_config),
    }


def get_minio_config() -> Dict[str, Any]:
    """
    Get MinIO configuration from Django settings.
    
    Returns:
        MinIO configuration dictionary
    """
    config = getattr(settings, 'QUICKWIT_CONFIG', {}).get('minio', {})

    return {
        'endpoint_url': config.get('endpoint_url', 'minio'),
        'endpoint_port': config.get('endpoint_port', '9000'),
        'access_key': config.get('access_key'),
        'secret_key': config.get('secret_key'),
        'bucket_name': config.get('bucket_name'),
        'secure': config.get('secure', False),
    }


def get_logging_config() -> Dict[str, Any]:
    """
    Get logging configuration for Quickwit integration.
    
    Returns:
        Logging configuration dictionary
    """
    quickwit_config = get_quickwit_config()

    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': 'django_quickwit_log.handlers.JSONFormatter',
                'app_name': quickwit_config['app_name'],
                'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}',
            },
        },
        'handlers': {
            'quickwit': {
                'level': 'INFO',
                'class': 'django_quickwit_log.handlers.QuickwitHandler',
                'app_name': quickwit_config['app_name'],
                'batch_size': quickwit_config['batch_size'],
                'flush_interval': quickwit_config['flush_interval'],
                'formatter': 'json',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['quickwit'],
                'level': 'INFO',
                'propagate': True,
            },
            'django.request': {
                'handlers': ['quickwit'],
                'level': 'ERROR',
                'propagate': True,
            },
        },
    }
