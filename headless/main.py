#!/usr/bin/env python3
"""
Headless VATSIM Tower Monitor
A background service version that monitors VATSIM for tower controllers without GUI.
Sends notifications via Pushover only.
"""

import sys
import signal
import logging
import atexit
import time
import os
import sys
from datetime import datetime

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils import load_artcc_roster, acquire_instance_lock, release_instance_lock
from config.config import load_config
from worker import HeadlessVATSIMWorker
from shared.notification_manager import NotificationManager


class HeadlessVATSIMMonitor:
    """Headless VATSIM Monitor - no GUI, Pushover notifications only"""

    def __init__(self):
        # Load configuration
        self.config = load_config()
        
        # Get airport configuration
        self.airport_config = self.config.get("airport", {})
        self.airport_code = self.airport_config.get("code", "KOAK")
        self.display_name = self.airport_config.get(
            "display_name", f"{self.airport_code} Main Facility"
        )

        # Application state
        self.current_status = "all_offline"
        self.controller_info = {}
        self.supporting_info = {}
        self.supporting_below_controllers = []
        self.last_check = None
        self.monitoring = False
        self._shutting_down = False
        
        # Store previous state information for consistent offline notifications
        self.previous_controller_info = []
        self.previous_supporting_info = []
        self.previous_supporting_below_controllers = []

        # Load ARTCC roster at startup
        self.controller_names = self.load_roster()

        # Setup components
        self.notification_manager = NotificationManager(self.config, self.controller_names)
        self.setup_worker()

        logging.info(f"Headless VATSIM {self.display_name} Monitor initialized")

    def load_roster(self):
        """Load ARTCC roster to translate CIDs to real names"""
        roster_url = self.config.get("api", {}).get(
            "roster_url", "https://oakartcc.org/about/roster"
        )
        return load_artcc_roster(roster_url)

    def setup_worker(self):
        """Setup the VATSIM worker thread"""
        self.worker = HeadlessVATSIMWorker(self.config)
        self.worker.status_updated_callback = self.on_status_updated
        self.worker.error_occurred_callback = self.on_error

    def on_status_updated(
        self, status, controller_info, supporting_info, supporting_below_controllers
    ):
        """Handle status update from worker thread"""
        previous_status = self.current_status
        
        # Store previous state information before updating
        self.previous_controller_info = self.controller_info if hasattr(self, 'controller_info') else []
        self.previous_supporting_info = self.supporting_info if hasattr(self, 'supporting_info') else []
        self.previous_supporting_below_controllers = self.supporting_below_controllers if hasattr(self, 'supporting_below_controllers') else []
        
        # Update current state
        self.current_status = status
        self.controller_info = controller_info
        self.supporting_info = supporting_info
        self.supporting_below_controllers = supporting_below_controllers
        self.last_check = datetime.now()

        # Log status change
        logging.info(f"Status changed from {previous_status} to {status}")

        # Send notification if status changed
        if status != previous_status:
            title, message, toast_type = self.notification_manager.get_transition_notification(
                previous_status,
                status,
                controller_info,
                supporting_info,
                supporting_below_controllers,
                self.previous_controller_info,
                self.previous_supporting_info,
                self.previous_supporting_below_controllers,
            )
            
            # Send Pushover notification
            self.notification_manager.send_pushover_notification(title, message, status)

    def on_error(self, error_message):
        """Handle error from worker thread"""
        logging.error(f"Worker error: {error_message}")

    def start_monitoring(self):
        """Start monitoring VATSIM"""
        if not self.monitoring:
            self.monitoring = True
            self.worker.start()
            logging.info("Started VATSIM monitoring")

    def stop_monitoring(self):
        """Stop monitoring VATSIM"""
        if self.monitoring:
            self.monitoring = False
            self.worker.stop()
            logging.info("Stopped VATSIM monitoring")

    def test_pushover(self):
        """Test Pushover notification"""
        return self.notification_manager.test_pushover()

    def shutdown(self):
        """Shutdown the monitor"""
        logging.info("Shutting down Headless VATSIM Monitor...")

        # Prevent multiple shutdown attempts
        if self._shutting_down:
            return
        self._shutting_down = True

        # Stop monitoring
        if self.monitoring:
            self.worker.stop()

        logging.info("Headless VATSIM Monitor shutdown complete")


# Global monitor instance for signal handler
monitor = None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global monitor
    logging.info("Received shutdown signal, shutting down gracefully...")
    if monitor is not None:
        monitor.shutdown()
    release_instance_lock()
    sys.exit(0)


def main():
    """Main entry point for headless monitor"""
    global monitor
    
    # Configure logging for headless operation
    handlers = []
    handlers.append(logging.StreamHandler())
    
    # Try to add file handler, but don't fail if we can't write to logs directory
    try:
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        handlers.append(logging.FileHandler("logs/vatsim_monitor_headless.log"))
        print("Logging to file: logs/vatsim_monitor_headless.log")
    except (PermissionError, OSError) as e:
        print(f"Warning: Cannot write to log file: {e}")
        print("Continuing with console logging only...")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    # Check for existing instance
    if not acquire_instance_lock():
        print("Another instance of Headless VATSIM Monitor is already running.")
        logging.info("Another instance detected, exiting...")
        sys.exit(0)

    # Register cleanup function to release lock on exit
    atexit.register(release_instance_lock)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        monitor = HeadlessVATSIMMonitor()

        # Test Pushover configuration at startup
        if monitor.notification_manager.pushover_service:
            logging.info("Testing Pushover configuration...")
            if monitor.test_pushover():
                logging.info("Pushover test successful - notifications will be sent")
            else:
                logging.warning("Pushover test failed - check configuration")
        else:
            logging.warning("Pushover not configured - no notifications will be sent!")

        # Start monitoring
        monitor.start_monitoring()

        logging.info(f"Headless VATSIM {monitor.display_name} Monitor started successfully")
        print(f"Headless VATSIM {monitor.display_name} Monitor is running...")
        print("Press Ctrl+C to stop")

        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        if monitor is not None:
            monitor.shutdown()
        release_instance_lock()


if __name__ == "__main__":
    main()