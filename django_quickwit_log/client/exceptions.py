class QuickwitError(Exception):
    """Base exception for Quickwit-related errors."""
    pass


class QuickwitConnectionError(QuickwitError):
    """Raised when unable to connect to Quickwit server."""
    pass


class QuickwitIndexError(QuickwitError):
    """Raised when index operations fail."""
    pass


class QuickwitDocumentError(QuickwitError):
    """Raised when document operations fail."""
    pass
