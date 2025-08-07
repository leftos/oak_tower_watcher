#!/usr/bin/env python3
"""
Main entry point for VATSIM Tower Monitor
A system tray application that monitors VATSIM for tower controllers.
"""

import sys
import signal
import logging
import atexit
import os

# Add parent directory to Python path to find shared and config modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils import acquire_instance_lock, release_instance_lock
from desktop.vatsim_monitor import VATSIMMonitor
from config.config import load_config
from shared.updater import check_for_updates

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/vatsim_monitor.log"), logging.StreamHandler()],
)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logging.info("Received Ctrl+C, shutting down gracefully...")
    release_instance_lock()
    sys.exit(0)


def main():
    """Main entry point"""
    # Check for existing instance
    if not acquire_instance_lock():
        print("Another instance of VATSIM Monitor is already running.")
        logging.info("Another instance detected, exiting...")
        sys.exit(0)

    # Register cleanup function to release lock on exit
    atexit.register(release_instance_lock)

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Load configuration for update check
        config = load_config()
        
        # Check for updates before starting the application
        try:
            success, message, updated = check_for_updates(config)
            if updated:
                logging.info(f"Application updated: {message}")
                print(f"Application updated: {message}")
                print("Please restart the application to use the new version.")
                release_instance_lock()
                sys.exit(0)
            elif not success:
                logging.warning(f"Update check failed: {message}")
            else:
                logging.info(f"Update check: {message}")
        except Exception as e:
            logging.error(f"Update check error: {e}")
            # Continue with application startup even if update check fails

        app = VATSIMMonitor(sys.argv)

        logging.info(f"Starting VATSIM Facility Watcher...")

        # Start monitoring automatically
        app.start_monitoring()

        # Run the application
        sys.exit(app.exec())

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
        release_instance_lock()
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        release_instance_lock()
        sys.exit(1)


if __name__ == "__main__":
    main()