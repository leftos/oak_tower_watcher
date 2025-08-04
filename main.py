#!/usr/bin/env python3
"""
Main entry point for VATSIM Tower Monitor
A system tray application that monitors VATSIM for tower controllers.
"""

import sys
import signal
import logging
import atexit
from utils import acquire_instance_lock, release_instance_lock
from vatsim_monitor import VATSIMMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("vatsim_monitor.log"), logging.StreamHandler()],
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
        app = VATSIMMonitor(sys.argv)

        logging.info(f"Starting VATSIM {app.display_name} Monitor...")

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
