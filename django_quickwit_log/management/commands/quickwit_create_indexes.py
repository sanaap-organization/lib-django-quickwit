from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from django_quickwit_log.client import QuickwitClient, QuickwitIndexError
from django_quickwit_log.config import get_quickwit_config


class Command(BaseCommand):
    """Create Quickwit indexes for Django apps."""
    
    help = 'Create Quickwit indexes for Django applications'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--app-name',
            type=str,
            help='Specific app name to create index for (default: all apps)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreate existing indexes',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )
    
    def handle(self, *args, **options):
        try:
            client = QuickwitClient()
            
            if not client.health_check():
                raise CommandError('Cannot connect to Quickwit server. Please check your configuration.')
            
            self.stdout.write(
                self.style.SUCCESS('Connected to Quickwit server')
            )
            
            config = get_quickwit_config()
            app_name = options.get('app_name') or config['app_name']
            force = options.get('force', False)
            dry_run = options.get('dry_run', False)
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN MODE - No indexes will be created')
                )
            
            # Create index for specified app or all apps
            if app_name:
                apps_to_process = [app_name]
            else:
                apps_to_process = [app for app in settings.INSTALLED_APPS 
                                 if not app.startswith('django.')]
            
            for app in apps_to_process:
                self._create_index_for_app(client, app, config, force, dry_run)
            
            self.stdout.write(
                self.style.SUCCESS('Index creation completed')
            )
            
        except Exception as e:
            raise CommandError(f'Error creating indexes: {e}')
    
    def _create_index_for_app(self, client, app_name, config, force, dry_run):
        """Create index for a specific app."""
        index_id = f"{config['index_prefix']}_{app_name}"
        
        # Check if index already exists
        try:
            existing_index = client.get_index_stats(index_id)
            if existing_index and not force:
                self.stdout.write(
                    self.style.WARNING(f'Index {index_id} already exists (use --force to recreate)')
                )
                return
            if existing_index and force:
                self.stdout.write(f'Deleting existing index: {index_id}')
                if not dry_run:
                    client.delete_index(index_id)
        except QuickwitIndexError:
            self.stdout.write(f'Creating index: {index_id}')

            if not dry_run:
                success = client.create_log_index(app_name)
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created index: {index_id}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to create index: {index_id}')
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Would create index: {index_id}')
                )
