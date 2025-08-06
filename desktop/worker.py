#!/usr/bin/env python3
"""
VATSIM API Worker module for VATSIM Tower Monitor
Handles background monitoring of VATSIM API for controller status.
This is the PyQt6-based threaded worker that uses the core VATSIM functionality.
"""

import logging
from PyQt6.QtCore import QThread, pyqtSignal
from shared.vatsim_core import VATSIMCore


class VATSIMWorker(QThread):
    """Worker thread for VATSIM API calls"""

    status_updated = pyqtSignal(
        str, list, list, list
    )  # status, main_facility_info, supporting_above_info, supporting_below_controllers
    force_check_completed = pyqtSignal(
        str, list, list, list
    )  # status, main_facility_info, supporting_above_info, supporting_below_controllers
    error_occurred = pyqtSignal(str)
    force_check_requested = pyqtSignal()  # Signal to request immediate check

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.running = False
        self.config = config
        self.check_interval = config.get("monitoring", {}).get("check_interval", 60)
        self.force_check_flag = False
        self.is_force_check = False

        # Create the core VATSIM client
        self.vatsim_core = VATSIMCore(config)

        # Connect the force check signal to the slot
        self.force_check_requested.connect(self.request_immediate_check)


    def set_interval(self, interval):
        """Set check interval"""
        self.check_interval = max(30, interval)  # Minimum 30 seconds

    def check_main_facility_status(self):
        """Check if main facility is online using the core client"""
        try:
            # Use the core VATSIM client to check status
            result = self.vatsim_core.check_status()
            
            if not result["success"]:
                # API error - emit error signal
                self.error_occurred.emit(result.get("error", "Unknown error"))
                return
            
            # Extract data from result
            status = result["status"]
            controller_info = result["main_controllers"]
            supporting_info = result["supporting_above"]
            supporting_below_controllers = result["supporting_below"]

            if self.is_force_check:
                self.force_check_completed.emit(
                    status, controller_info, supporting_info, supporting_below_controllers
                )
                self.is_force_check = False
            else:
                self.status_updated.emit(
                    status, controller_info, supporting_info, supporting_below_controllers
                )
                
        except Exception as e:
            logging.error(f"Error in check_main_facility_status: {e}")
            self.error_occurred.emit(f"Status check error: {str(e)}")

    def request_immediate_check(self):
        """Slot to handle force check requests"""
        self.force_check_flag = True
        self.is_force_check = True

    def run(self):
        """Main monitoring loop"""
        self.running = True
        while self.running:
            try:
                self.check_main_facility_status()

                # Sleep in small intervals to allow quick response to stop signals and force checks
                sleep_time = self.check_interval * 1000  # Convert to milliseconds
                sleep_chunk = 500  # Sleep in 500ms chunks

                while sleep_time > 0 and self.running:
                    # Check if force check was requested
                    if self.force_check_flag:
                        self.force_check_flag = False
                        logging.info("Force check requested, breaking sleep cycle")
                        break

                    chunk_size = min(sleep_chunk, sleep_time)
                    self.msleep(chunk_size)
                    sleep_time -= chunk_size

            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                self.error_occurred.emit(f"Monitoring Error: {str(e)}")

                # Also sleep in chunks during error recovery
                sleep_time = self.check_interval * 1000
                sleep_chunk = 500

                while sleep_time > 0 and self.running:
                    # Check if force check was requested during error recovery too
                    if self.force_check_flag:
                        self.force_check_flag = False
                        logging.info(
                            "Force check requested during error recovery, breaking sleep cycle"
                        )
                        break

                    chunk_size = min(sleep_chunk, sleep_time)
                    self.msleep(chunk_size)
                    sleep_time -= chunk_size

    def stop(self):
        """Stop the worker thread"""
        self.running = False
        self.quit()
        # Wait for thread to finish - should be quick now with chunked sleep
        self.wait(2000)  # 2 second timeout should be plenty