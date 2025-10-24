import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from minio import Minio
from minio.error import S3Error

from .exceptions import StorageConnectionError, StorageUploadError
from ..config import get_minio_config

logger = logging.getLogger(__name__)


class MinIOStorage:
    """
    MinIO storage client for managing log files.
    
    This client provides methods for uploading, downloading, and managing
    log files in MinIO object storage.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize MinIO storage client.
        
        Args:
            config: MinIO configuration dictionary. If not provided, uses Django settings.
        """
        if config is None:
            config = get_minio_config()

        self.endpoint = config.get('endpoint_url')
        if config.get("endpoint_port"):
            self.endpoint += f":{config.get("endpoint_port")}"
        self.access_key = config.get('access_key')
        self.secret_key = config.get('secret_key')
        self.bucket_name = config.get('bucket_name')
        self.secure = config.get('secure')

        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            self._ensure_bucket_exists()
        except Exception as e:
            raise StorageConnectionError(f"Failed to initialize MinIO client: {e}")

    def _ensure_bucket_exists(self) -> None:
        """Ensure the bucket exists, create if it doesn't."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
        except S3Error as e:
            raise StorageConnectionError(f"Failed to create bucket {self.bucket_name}: {e}")

    def health_check(self) -> bool:
        """
        Check if MinIO storage is accessible.
        
        Returns:
            True if storage is accessible, False otherwise
        """
        try:
            return self.client.bucket_exists(self.bucket_name)
        except Exception:
            return False

    def upload_file(self, local_path: str, object_name: str,
                    content_type: str = 'application/json') -> str:
        """
        Upload a file to MinIO storage.
        
        Args:
            local_path: Path to local file
            object_name: Name for the object in storage
            content_type: MIME type of the file
            
        Returns:
            Object URL in storage
            
        Raises:
            StorageUploadError: If upload fails
        """
        try:
            if not os.path.exists(local_path):
                raise StorageUploadError(f"Local file not found: {local_path}")

            self.client.fput_object(
                self.bucket_name,
                object_name,
                local_path,
                content_type=content_type
            )

            object_url = f"{'https' if self.secure else 'http'}://{self.endpoint}/{self.bucket_name}/{object_name}"
            logger.info(f"Uploaded file: {local_path} -> {object_url}")
            return object_url

        except S3Error as e:
            raise StorageUploadError(f"Failed to upload {local_path}: {e}")
        except Exception as e:
            raise StorageUploadError(f"Unexpected error uploading {local_path}: {e}")

    def list_objects(self, prefix: str = '') -> List[Dict[str, Any]]:
        """
        List objects in the bucket.
        
        Args:
            prefix: Object name prefix to filter by
            
        Returns:
            List of object information dictionaries
        """
        try:
            objects = []
            for obj in self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True):
                objects.append({
                    'name': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified,
                    'etag': obj.etag
                })
            return objects
        except S3Error as e:
            logger.error(f"Failed to list objects with prefix {prefix}: {e}")
            return []

    def upload_log_file(self, app_name: str, log_file_path: str) -> str:
        """
        Upload a Django log file to MinIO with organized naming.
        
        Args:
            app_name: Django app name
            log_file_path: Path to the log file
            
        Returns:
            Object URL in storage
        """
        file_name = os.path.basename(log_file_path)
        timestamp = datetime.now().strftime('%Y/%m/%d')
        object_name = f"logs/{app_name}/{timestamp}/{file_name}"

        return self.upload_file(log_file_path, object_name)

    def sync_logs_directory(self, app_name: str, logs_dir: str) -> List[str]:
        """
        Sync all log files from a directory to MinIO.
        
        Args:
            app_name: Django app name
            logs_dir: Path to logs directory
            
        Returns:
            List of uploaded object URLs
        """
        uploaded_urls = []
        logs_path = Path(logs_dir)

        if not logs_path.exists():
            logger.warning(f"Logs directory does not exist: {logs_dir}")
            return uploaded_urls

        for log_file in logs_path.glob('*.json'):
            try:
                url = self.upload_log_file(app_name, str(log_file))
                uploaded_urls.append(url)
            except StorageUploadError as e:
                logger.error(f"Failed to upload {log_file}: {e}")

        for log_file in logs_path.glob('*.log'):
            try:
                url = self.upload_log_file(app_name, str(log_file))
                uploaded_urls.append(url)
            except StorageUploadError as e:
                logger.error(f"Failed to upload {log_file}: {e}")

        logger.info(f"Synced {len(uploaded_urls)} log files for app {app_name}")
        return uploaded_urls
