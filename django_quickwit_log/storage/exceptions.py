class StorageError(Exception):
    """Base exception for storage-related errors."""
    pass


class StorageConnectionError(StorageError):
    """Raised when unable to connect to storage service."""
    pass


class StorageUploadError(StorageError):
    """Raised when file upload fails."""
    pass


class StorageDownloadError(StorageError):
    """Raised when file download fails."""
    pass
