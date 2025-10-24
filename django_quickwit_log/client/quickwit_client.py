import json
import logging
import requests
from typing import Dict, List, Optional, Any, BinaryIO
from urllib.parse import urljoin

from .exceptions import QuickwitError, QuickwitConnectionError, QuickwitIndexError
from django_quickwit_log.config import get_quickwit_config
from ..utils.constants import default_index_config

logger = logging.getLogger(__name__)


class QuickwitClient:
    """
    Client for interacting with Quickwit server.
    
    This client provides methods for creating indexes, indexing documents,
    and searching through indexed data.
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize Quickwit client.
        
        Args:
            base_url: Quickwit server URL. If not provided, uses Django settings.
        """
        self.config = get_quickwit_config()

        self.server_url = base_url or self.config.get("url")
        self.base_url = f"{self.server_url.rstrip('/')}/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

        self._index_cache = {}

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request to Quickwit server.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            Response object
            
        Raises:
            QuickwitConnectionError: If connection fails
        """
        url = urljoin(self.base_url.rstrip('/') + '/', endpoint.lstrip('/'))

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError as e:
            raise QuickwitConnectionError(f"Failed to connect to Quickwit at {self.base_url}: {e}")
        except requests.exceptions.HTTPError as e:
            try:
                error_body = response.text
            except Exception:
                error_body = ''
            if response.status_code == 404:
                raise QuickwitIndexError(f"Index not found: {e}")
            raise QuickwitError(f"Quickwit API error: {e}; body={error_body}")
        except requests.exceptions.RequestException as e:
            raise QuickwitError(f"Request failed: {e}")

    def health_check(self) -> bool:
        """
        Check if Quickwit server is healthy.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            for path in ("/health/livez", "/health/readyz"):
                try:
                    response = self.session.get(f"{self.server_url.rstrip('/')}{path}", timeout=5)
                    if response.status_code == 200:
                        return True
                except requests.exceptions.RequestException:
                    continue
            return False
        except Exception:
            return False

    def list_indexes(self) -> List[Dict[str, Any]]:
        """
        List all available indexes.
        
        Returns:
            List of index information dictionaries
        """
        response = self._make_request('GET', '/indexes')
        return response.json()

    def create_index(self, index_config: Dict[str, Any]) -> bool:
        """
        Create a new index.
        
        Args:
            index_config: Index configuration
            
        Returns:
            True if index was created successfully
            
        Raises:
            QuickwitIndexError: If index creation fails
        """
        try:
            self._make_request('POST', f'/indexes', json=index_config)
            logger.info(f"Successfully created index")
            return True
        except QuickwitError as e:
            logger.error(f"Failed to create index: {e}")
            raise

    def delete_index(self, index_id: str) -> bool:
        """
        Delete an index.
        
        Args:
            index_id: Index identifier
            
        Returns:
            True if index was deleted successfully

        Raises:
            QuickwitError: If index deletion fails
        """
        try:
            self._make_request('DELETE', f'/indexes/{index_id}')
            logger.info(f"Successfully deleted index: {index_id}")
            return True
        except QuickwitError as e:
            logger.error(f"Failed to delete index {index_id}: {e}")
            raise

    def clear_index(self, index_id: str) -> bool:
        """
        Clears documents of index id.
        all splits will be deleted (metastore + storage) and all source checkpoints will be reset.
        
        Args:
            index_id: Index identifier
            
        Returns:
            True if index was cleared successfully

        Raises:
            QuickwitError: If index clearing fails
        """
        try:
            self._make_request('PUT', f'/indexes/{index_id}/clear')
            logger.info(f"Successfully cleared index: {index_id}")
            return True
        except QuickwitError as e:
            logger.error(f"Failed to clear index {index_id}: {e}")
            raise

    def get_index_stats(self, index_id: str) -> Dict[str, Any]:
        """
        The response is the stats about the requested index
        
        Args:
            index_id: Index identifier
            
        Returns:
            Index statistics dictionary
        """
        response = self._make_request('GET', f'/indexes/{index_id}/describe')
        return response.json()

    def create_log_index(self, app_name: str, index_config: Dict = None) -> bool:
        """
        Create a log index for a Django app.
        
        Args:
            app_name: Django app name
            index_config: index configuration dictionary (if None, a default config is used)

        Returns:
            True if index was created successfully
        """
        index_id = f"{self.config.get("index_prefix")}_{app_name}"
        # Check if index already exists
        try:
            if self.get_index_stats(index_id):
                logger.info(f"Index {index_id} already exists")
                return True
        except QuickwitIndexError:
            if not index_config:
                index_config = default_index_config

            index_config["index_id"] = index_id
            return self.create_index(index_config)
        except Exception:
            raise

    def index_documents(self, index_id: str, documents: List[Dict[str, Any]], commit: str = 'auto') -> bool:
        """
        Index a batch of documents into an index using NDJSON payload.

        Args:
            index_id: Index identifier
            documents: List of documents (dicts)
            commit: Commit behavior ('auto' or 'force')

        Returns:
            True if documents were indexed successfully
        """
        try:
            ndjson_lines = [json.dumps(doc, ensure_ascii=False) for doc in documents]
            payload = ("\n".join(ndjson_lines) + "\n").encode('utf-8')

            self._make_request(
                'POST',
                f'/{index_id}/ingest',
                params={'commit': commit},
                headers={'Content-Type': 'application/x-ndjson'},
                data=payload,
            )
            logger.info(f"Successfully indexed {len(documents)} documents into index: {index_id}")
            return True
        except QuickwitError as e:
            logger.error(f"Failed to index documents into index {index_id}: {e}")
            raise

    def index_document(self, index_id: str, document: Dict[str, Any], commit: str = 'auto') -> bool:
        """
        Index a single document into an index.

        Args:
            index_id: Index identifier
            document: Document dict
            commit: Commit behavior ('auto' or 'force')

        Returns:
            True if the document was indexed successfully
        """
        return self.index_documents(index_id, [document], commit)

    def search(self, index_id: str, query: str, **kwargs) -> Dict[str, Any]:
        """
        Search documents in an index.
        
        Args:
            index_id: Index identifier
            query: Search query (query language doc: https://quickwit.io/docs/reference/query-language)
            **kwargs: Additional search parameters
            
        Returns:
            Search results dictionary
        """
        search_params = {
            'query': query,
            **kwargs
        }

        response = self._make_request('GET', f'/{index_id}/search',
                                      params=search_params)
        return response.json()

    def create_doc_delete_task(self, index_id: str, query: str, search_field: List[str] = None,
                               start_timestamp: int = None, end_timestamp: int = None):
        """
        Create a delete task that will delete all documents matching the provided query in the given index <index id>. 
        The endpoint simply appends your delete task to the delete task queue in the metastore. 
        The deletion will eventually be executed.

        Args:
            index_id: Index identifier
            query: Search query (query language doc: https://quickwit.io/docs/reference/query-language)
            search_field: List of search fields
            start_timestamp: Start timestamp
            end_timestamp: End timestamp
            
        Returns:
            True if delete task was created successfully
        
        """

        try:
            payload = {
                'query': query,
                "search_field": search_field,
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp
            }
            self._make_request('POST', f'/indexes/{index_id}/delete-tasks', json=payload)
            logger.info(f"Successfully created delete task for index: {index_id}")
            return True
        except QuickwitError as e:
            logger.error(f"Failed to create delete task for index {index_id}: {e}")
            raise

    def ingest_json_file(self, index_id: str, json_file: BinaryIO, commit: str = 'auto') -> bool:
        """
        Ingest documents into an index.

        Args:
            index_id: Index identifier
            json_file: BinaryIO of the json file
            commit: Commit behavior ('auto' or 'force')

        Returns:
            True if json file was ingested successfully
        """
        try:
            self._make_request('POST', f'/{index_id}/ingest',
                               params={'commit': commit},
                               headers={'Content-Type': 'application/x-ndjson'},
                               data=json_file,
                               )
            logger.info(f"Successfully ingested {json_file} into index: {index_id}")
            return True
        except QuickwitError as e:
            logger.error(f"Failed to ingest documents into index {index_id}: {e}")
            raise

    def ingest_json_file_path(self, index_id: str, file_path: str) -> bool:
        """
        Ingest documents into an index from a file path.

        Args:
            index_id: Index identifier
            file_path: Path to a JSON/NDJSON file to ingest

        Returns:
            True if the file was ingested successfully
        """
        with open(file_path, 'rb') as file_handle:
            return self.ingest_json_file(index_id, file_handle)
