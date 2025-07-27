#!/usr/bin/env python3
"""
Simplified TikTok Scraper - Clean Architecture Version
Replaces the complex robust_master_downloader.py with clean, modular design
"""

import sys
import os
import asyncio
from pathlib import Path

# Add core module to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import TikTokConfig, create_argument_parser
from core.processor import create_and_run_processor
from core.multiprocess import run_multiprocess_processing
from core.exceptions import ErrorHandler, TikTokScraperException


def show_banner():
    """Display application banner"""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║  ████████╗██╗██╗  ██╗████████╗ ██████╗ ██╗  ██╗                ║
║  ╚══██╔══╝██║██║ ██╔╝╚══██╔══╝██╔═══██╗██║ ██╔╝                ║
║     ██║   ██║█████╔╝    ██║   ██║   ██║█████╔╝                 ║
║     ██║   ██║██╔═██╗    ██║   ██║   ██║██╔═██╗                 ║
║     ██║   ██║██║  ██╗   ██║   ╚██████╔╝██║  ██╗                ║
║     ╚═╝   ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝                ║
║                                                                ║
║   ███████╗ ██████╗██████╗  █████╗ ██████╗ ███████╗██████╗      ║
║   ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗     ║
║   ███████╗██║     ██████╔╝███████║██████╔╝█████╗  ██████╔╝     ║
║   ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗     ║
║   ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗██║  ██║     ║
║   ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝     ║
║                                                                ║
║                         Clean Architecture v3.0               ║
║                     Unified & Simplified                      ║
╚════════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print("🚀 Advanced TikTok Video Downloader & Comment Extractor")
    print("📚 Clean, modular architecture with unified components")
    print()


def handle_no_args_defaults(config: TikTokConfig) -> TikTokConfig:
    """Apply default settings when no arguments provided"""
    print("🔧 No arguments provided - using default settings:")
    print("   --from-file urls.txt --mp3 --whisper --batch-size 10 --delay 2 --max-comments 10")
    print()
    
    # Apply defaults
    config.input_file = 'urls.txt'
    config.audio_only = True
    config.use_whisper = True
    config.batch_size = 10
    config.delay = 2.0
    config.max_comments = 10
    
    # Check for MS_TOKEN in environment if not provided
    if not config.ms_token:
        config.ms_token = os.getenv('MS_TOKEN') or os.getenv('TIKTOK_MS_TOKEN')
        if config.ms_token:
            print(f"✅ MS_TOKEN loaded from environment")
    
    return config


async def main():
    """Main entry point"""
    # Show banner
    show_banner()
    
    # Parse command line arguments
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Create configuration
    try:
        if hasattr(args, 'config') and args.config:
            # Load from config file
            config = TikTokConfig.from_file(args.config)
        else:
            # Create from command line args
            config = TikTokConfig.from_args(args)
        
        # Handle no arguments case (apply defaults)
        if len(sys.argv) == 1 or (not config.url and not config.input_file):
            config = handle_no_args_defaults(config)
        
        # Save config if requested
        if hasattr(args, 'save_config') and args.save_config:
            if config.save_to_file(args.save_config):
                print(f"✅ Configuration saved to {args.save_config}")
            else:
                print(f"❌ Failed to save configuration to {args.save_config}")
            return
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Initialize error handler
    error_handler = ErrorHandler(verbose=config.verbose)
    
    # Setup debug logging if enabled
    if config.debug:
        debug_dir = "debug-logs"  # Local directory, not root
        os.makedirs(debug_dir, exist_ok=True)
        
        import logging
        from datetime import datetime
        
        # Create debug log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = os.path.join(debug_dir, f"tiktok_scraper_debug_{timestamp}.log")
        
        # Setup file logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            handlers=[
                logging.FileHandler(debug_file),
                logging.StreamHandler()  # Also keep console output
            ]
        )
        
        print(f"🐛 Debug logging enabled: {debug_file}")
    
    try:
        # Validate configuration
        config.validate()
        
        # Display configuration
        error_handler.handle_info(f"Configuration: {config}", "Setup")
        
        # Choose processing mode
        if config.workers > 1:
            # Multiprocess mode - handles its own signals, don't wrap in try-catch
            error_handler.handle_info(
                f"Using multiprocess mode with {config.workers} workers",
                "Setup"
            )
            
            if not config.input_file:
                raise TikTokScraperException(
                    "Multiprocess mode requires --from-file option"
                )
            
            summary = await run_multiprocess_processing(config)
        else:
            # Single process mode - processor handles its own signals and shutdown
            error_handler.handle_info("Using single process mode", "Setup")
            summary = await create_and_run_processor(config)
        
        # Final status
        if summary.successful_count > 0:
            error_handler.handle_success(
                f"Processing completed successfully - {summary.successful_count} videos processed",
                "Complete"
            )
        else:
            error_handler.handle_warning("No videos were processed successfully", "Complete")
    except TikTokScraperException as e:
        error_handler.handle_error(e, "Application", critical=True)
        sys.exit(1)
    except Exception as e:
        error_handler.handle_error(
            TikTokScraperException("Unexpected error occurred", original_error=e),
            "Application",
            critical=True
        )
        sys.exit(1)


if __name__ == "__main__":
    # Handle asyncio on Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())