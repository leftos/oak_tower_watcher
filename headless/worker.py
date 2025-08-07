#!/usr/bin/env python3
"""
Headless VATSIM API Worker module for VATSIM Tower Monitor
Handles background monitoring of VATSIM API for controller status without PyQt6 dependencies.
"""

import logging
import threading
import time
import sys
import os
from typing import Callable, Optional

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.vatsim_core import VATSIMCore


class HeadlessVATSIMWorker:
    """Headless worker for VATSIM API calls using threading instead of QThread"""

    def __init__(self, config):
        self.running = False
        self.config = config
        self.check_interval = config.get("monitoring", {}).get("check_interval", 60)
        self.force_check_flag = False
        self.is_force_check = False
        self.thread = None

        # Callback functions (set by parent)
        self.status_updated_callback: Optional[Callable] = None
        self.error_occurred_callback: Optional[Callable] = None

        # Create the shared VATSIM core client
        self.vatsim_core = VATSIMCore(config)

    def set_interval(self, interval):
        """Set check interval"""
        self.check_interval = max(30, interval)  # Minimum 30 seconds

    def check_main_facility_status(self):
        """Check if main facility is online using the shared core client"""
        try:
            # Use the shared VATSIM core client to check status
            result = self.vatsim_core.check_status()
            
            if not result["success"]:
                # API error - emit error callback
                if self.error_occurred_callback:
                    self.error_occurred_callback(result.get("error", "Unknown error"))
                return
            
            # Extract data from result
            status = result["status"]
            controller_info = result["main_controllers"]
            supporting_info = result["supporting_above"]
            supporting_below_controllers = result["supporting_below"]

            # Call the status updated callback
            if self.status_updated_callback:
                self.status_updated_callback(
                    status, controller_info, supporting_info, supporting_below_controllers
                )
                
        except Exception as e:
            logging.error(f"Error in check_main_facility_status: {e}")
            if self.error_occurred_callback:
                self.error_occurred_callback(f"Status check error: {str(e)}")

    def request_immediate_check(self):
        """Request an immediate check"""
        self.force_check_flag = True
        self.is_force_check = True

    def _run_loop(self):
        """Main monitoring loop"""
        self.running = True
        while self.running:
            try:
                self.check_main_facility_status()

                # Sleep in small intervals to allow quick response to stop signals and force checks
                sleep_time = self.check_interval
                sleep_chunk = 0.5  # Sleep in 0.5 second chunks

                while sleep_time > 0 and self.running:
                    # Check if force check was requested
                    if self.force_check_flag:
                        self.force_check_flag = False
                        logging.info("Force check requested, breaking sleep cycle")
                        break

                    chunk_size = min(sleep_chunk, sleep_time)
                    time.sleep(chunk_size)
                    sleep_time -= chunk_size

            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                if self.error_occurred_callback:
                    self.error_occurred_callback(f"Monitoring Error: {str(e)}")

                # Also sleep in chunks during error recovery
                sleep_time = self.check_interval
                sleep_chunk = 0.5

                while sleep_time > 0 and self.running:
                    # Check if force check was requested during error recovery too
                    if self.force_check_flag:
                        self.force_check_flag = False
                        logging.info(
                            "Force check requested during error recovery, breaking sleep cycle"
                        )
                        break

                    chunk_size = min(sleep_chunk, sleep_time)
                    time.sleep(chunk_size)
                    sleep_time -= chunk_size

    def start(self):
        """Start the worker thread"""
        if not self.running:
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logging.info("Headless VATSIM worker started")

    def stop(self):
        """Stop the worker thread"""
        if self.running:
            self.running = False
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=2.0)  # Wait up to 2 seconds
            logging.info("Headless VATSIM worker stopped")