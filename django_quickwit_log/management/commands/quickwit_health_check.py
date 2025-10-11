from django.core.management.base import BaseCommand

from django_quickwit_log.client import QuickwitClient
from django_quickwit_log.storage import MinIOStorage
from django_quickwit_log.config import get_quickwit_config, get_minio_config


class Command(BaseCommand):
    """Check health of Quickwit and MinIO services."""
    
    help = 'Check health of Quickwit and MinIO services'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--quickwit-only',
            action='store_true',
            help='Only check Quickwit health',
        )
        parser.add_argument(
            '--minio-only',
            action='store_true',
            help='Only check MinIO health',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information',
        )
    
    def handle(self, *args, **options):
        quickwit_only = options.get('quickwit_only', False)
        minio_only = options.get('minio_only', False)
        verbose = options.get('verbose', False)
        
        self.stdout.write('Checking service health...\n')
        
        if not minio_only:
            self._check_quickwit(verbose)
        
        if not quickwit_only:
            self._check_minio(verbose)
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Health check completed'))
    
    def _check_quickwit(self, verbose):
        """Check Quickwit service health."""
        self.stdout.write('Quickwit Service:')
        
        try:
            client = QuickwitClient()
            
            if client.health_check():
                self.stdout.write('  Status: ' + self.style.SUCCESS(' HEALTHY'))
                
                if verbose:
                    config = get_quickwit_config()
                    self.stdout.write(f'  URL: {config["url"]}')
                    self.stdout.write(f'  Index Prefix: {config["index_prefix"]}')
                    
                    # List indexes
                    try:
                        indexes = client.list_indexes()
                        self.stdout.write(f'  Indexes: {len(indexes)} found')
                        
                        for index in indexes:
                            index_id = index.get('index_id', 'unknown')
                            self.stdout.write(f'    - {index_id}')
                            
                            if verbose:
                                try:
                                    stats = client.get_index_stats(index_id)
                                    doc_count = stats.get('num_docs', 0)
                                    self.stdout.write(f'      Documents: {doc_count}')
                                except Exception:
                                    pass
                    except Exception as e:
                        self.stdout.write(f'  Error listing indexes: {e}')
            else:
                self.stdout.write('  Status: ' + self.style.ERROR(' UNHEALTHY'))
                
        except Exception as e:
            self.stdout.write('  Status: ' + self.style.ERROR(' ERROR'))
            self.stdout.write(f'  Error: {e}')
    
    def _check_minio(self, verbose):
        """Check MinIO service health."""
        self.stdout.write('\nMinIO Storage:')
        
        try:
            client = MinIOStorage()
            
            if client.health_check():
                self.stdout.write('  Status: ' + self.style.SUCCESS(' HEALTHY'))
                
                if verbose:
                    config = get_minio_config()
                    self.stdout.write(f'  Endpoint: {config["endpoint"]}')
                    self.stdout.write(f'  Bucket: {config["bucket_name"]}')
                    self.stdout.write(f'  Secure: {config["secure"]}')
                    
                    # List objects
                    try:
                        objects = client.list_objects()
                        self.stdout.write(f'  Objects: {len(objects)} found')
                        
                        if verbose and objects:
                            # Show recent objects
                            recent_objects = sorted(
                                objects, 
                                key=lambda x: x.get('last_modified', ''), 
                                reverse=True
                            )[:5]
                            
                            self.stdout.write('  Recent objects:')
                            for obj in recent_objects:
                                name = obj.get('name', 'unknown')
                                size = obj.get('size', 0)
                                modified = obj.get('last_modified', 'unknown')
                                self.stdout.write(f'    - {name} ({size} bytes, {modified})')
                    except Exception as e:
                        self.stdout.write(f'  Error listing objects: {e}')
            else:
                self.stdout.write('  Status: ' + self.style.ERROR(' UNHEALTHY'))
                
        except Exception as e:
            self.stdout.write('  Status: ' + self.style.ERROR(' ERROR'))
            self.stdout.write(f'  Error: {e}')
