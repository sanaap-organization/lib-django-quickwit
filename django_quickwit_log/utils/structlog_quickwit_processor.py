import logging

from django_quickwit_log.config import get_quickwit_config
from ..client import QuickwitClient


class QuickwitProcessor:
    """
    Structlog processor that can send logs to Quickwit based on a parameter.
    """

    def __init__(self, app_name: str = None):
        """
        Initialize the processor.
        
        Args:
            app_name: Django app name (defaults to config)
        """
        self.config = get_quickwit_config()
        self.app_name = app_name or self.config.get('app_name')
        self.quickwit_client = QuickwitClient()

    def __call__(self, logger, method_name, event_dict):
        """
        Process the log event and optionally send to Quickwit.
        
        Args:
            logger: Logger instance
            method_name: Log method name (info, error, etc.)
            event_dict: Log event dictionary
            
        Returns:
            Modified event dictionary
        """
        # Check if this log should be sent to Quickwit
        send_to_quickwit = event_dict.pop('send_to_quickwit', False)

        if send_to_quickwit and self.config.get('enable_quickwit_indexing', True):
            try:
                self.quickwit_client.create_log_index(self.app_name)

                quickwit_data = event_dict.copy()
                if 'app_name' not in quickwit_data:
                    quickwit_data['app_name'] = self.app_name

                index_id = f"{self.config.get("index_prefix")}_{self.app_name}"
                self.quickwit_client.index_document(index_id, quickwit_data, commit='force')

            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to send log to Quickwit: {e}")

        return event_dict


def add_quickwit_processor(app_name: str = None):
    """
    Lazy wrapper so QuickwitProcessor is only instantiated when logging occurs.
    """

    def _processor(logger, method_name, event_dict):
        processor = QuickwitProcessor(app_name)
        return processor(logger, method_name, event_dict)

    return _processor
