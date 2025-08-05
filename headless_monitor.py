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
from datetime import datetime
from utils import acquire_instance_lock, release_instance_lock, load_artcc_roster
from config import load_config
from headless_worker import HeadlessVATSIMWorker
from notification_manager import NotificationManager


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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("vatsim_monitor_headless.log"),
            logging.StreamHandler()
        ],
    )

    # Check for existing instance
    if not acquire_instance_lock():
        print("Another instance of VATSIM Monitor is already running.")
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