from django.core.management.base import BaseCommand
from server.services import CollectorService
import subprocess
import os


class Command(BaseCommand):
    help = 'Process TikTok URLs using collector.py'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='Single TikTok URL to process'
        )
        parser.add_argument(
            '--from-file',
            type=str,
            help='File containing URLs (one per line)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of URLs to process in batch'
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=4,
            help='Number of worker processes'
        )
        parser.add_argument(
            '--whisper',
            action='store_true',
            help='Use Whisper for transcription'
        )
        parser.add_argument(
            '--mp3',
            action='store_true',
            help='Download audio only as MP3'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution"""
        
        if options['url']:
            # Process single URL
            self.stdout.write(f"Processing URL: {options['url']}")
            CollectorService.queue_url(options['url'])
            CollectorService.trigger_processing([options['url']], options['workers'])
            
        elif options['from_file']:
            # Process URLs from file
            if os.path.exists(options['from_file']):
                with open(options['from_file'], 'r') as f:
                    urls = [line.strip() for line in f if line.strip()]
                
                self.stdout.write(f"Processing {len(urls)} URLs from {options['from_file']}")
                CollectorService.queue_multiple_urls(urls)
                CollectorService.trigger_processing(urls, options['workers'])
            else:
                self.stderr.write(f"File not found: {options['from_file']}")
                
        else:
            # Process batch from queue
            self.stdout.write(f"Processing batch of {options['batch_size']} URLs")
            process = CollectorService.batch_process(
                batch_size=options['batch_size'],
                workers=options['workers']
            )
            
            if process:
                self.stdout.write(self.style.SUCCESS('Batch processing started'))
                # Wait for process to complete
                process.wait()
                self.stdout.write(self.style.SUCCESS('Batch processing completed'))
            else:
                self.stdout.write('No pending URLs to process')