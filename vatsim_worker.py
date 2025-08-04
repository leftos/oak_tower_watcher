#!/usr/bin/env python3
"""
VATSIM API Worker module for VATSIM Tower Monitor
Handles background monitoring of VATSIM API for controller status.

Regex-based Callsign Matching:
- Uses regex patterns from configuration to match controller callsigns
- Supports multiple controllers matching the same pattern (e.g., OAK_TWR, OAK_1_TWR, OAK_2_TWR)
- Each matched controller is captured as a separate controller instance
- Patterns are compiled once for performance and use case-insensitive matching
"""

import requests
import json
import logging
import re
from PyQt6.QtCore import QThread, pyqtSignal


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

        # Load API endpoints from config
        api_config = config.get("api", {})
        self.vatsim_api_url = api_config.get(
            "vatsim_url", "https://data.vatsim.net/v3/vatsim-data.json"
        )

        # Load callsign regex patterns from config
        callsigns = config.get("callsigns", {})
        self.main_facility_patterns = callsigns.get(
            "main_facility", [r"^OAK_(?:\d+_)?TWR$"]
        )
        self.supporting_above_patterns = callsigns.get(
            "supporting_above", [r"^NCT_APP$", r"^OAK_\d+_CTR$"]
        )
        self.supporting_below_patterns = callsigns.get(
            "supporting_below", [r"^OAK_(?:\d+_)?GND$"]
        )

        # Compile regex patterns for better performance (case-insensitive matching)
        # This allows capturing multiple controllers matching the same pattern
        # e.g., OAK_TWR, OAK_1_TWR, OAK_2_TWR all match ^OAK_(?:\d+_)?TWR$
        self.main_facility_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.main_facility_patterns
        ]
        self.supporting_above_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.supporting_above_patterns
        ]
        self.supporting_below_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.supporting_below_patterns
        ]

        # Connect the force check signal to the slot
        self.force_check_requested.connect(self.request_immediate_check)

    def is_controller_active(self, controller):
        """Check if a controller is active (not on inactive frequency 199.998)"""
        frequency = controller.get("frequency", "")
        # Convert frequency to string for comparison to handle both string and numeric types
        return str(frequency) != "199.998"

    def set_interval(self, interval):
        """Set check interval"""
        self.check_interval = max(30, interval)  # Minimum 30 seconds

    def query_vatsim_api(self):
        """Query VATSIM API for controller data"""
        try:
            logging.info("Querying VATSIM API...")
            response = requests.get(self.vatsim_api_url, timeout=10)
            response.raise_for_status()

            data = response.json()
            controllers = data.get("controllers", [])

            # Look for main facility controllers
            main_facility_controllers = []
            supporting_above_controllers = []
            supporting_below_controllers = []

            for controller in controllers:
                callsign = controller.get("callsign", "")

                # Skip inactive controllers (frequency 199.998)
                if not self.is_controller_active(controller):
                    freq = controller.get('frequency', 'Unknown')
                    logging.debug(f"Skipping inactive controller {callsign} (freq: {freq})")
                    continue

                # Check for main facility controllers using regex patterns
                # This captures all controllers matching any main facility pattern
                # e.g., OAK_TWR, OAK_1_TWR, OAK_2_TWR, etc.
                if any(regex.match(callsign) for regex in self.main_facility_regex):
                    main_facility_controllers.append(controller)

                # Check for supporting above facility controllers using regex patterns
                # e.g., NCT_APP, OAK_36_CTR, OAK_62_CTR, etc.
                elif any(
                    regex.match(callsign) for regex in self.supporting_above_regex
                ):
                    supporting_above_controllers.append(controller)

                # Check for supporting below controllers using regex patterns
                # e.g., OAK_GND, OAK_1_GND, OAK_2_GND, etc.
                elif any(
                    regex.match(callsign) for regex in self.supporting_below_regex
                ):
                    supporting_below_controllers.append(controller)

            return (
                main_facility_controllers,
                supporting_above_controllers,
                supporting_below_controllers,
            )

        except requests.exceptions.RequestException as e:
            logging.error(f"Error querying VATSIM API: {e}")
            self.error_occurred.emit(f"API Error: {str(e)}")
            return None, None, None
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing VATSIM API response: {e}")
            self.error_occurred.emit(f"JSON Error: {str(e)}")
            return None, None, None

    def check_main_facility_status(self):
        """Check if main facility is online"""
        (
            main_facility_controllers,
            supporting_above_controllers,
            supporting_below_controllers,
        ) = self.query_vatsim_api()

        if (
            main_facility_controllers is None
            and supporting_above_controllers is None
            and supporting_below_controllers is None
        ):
            # API error - don't change status
            return

        # Determine status based on what's online
        if main_facility_controllers and supporting_above_controllers:
            # Both main facility and supporting above facilities online - highest priority
            status = "main_facility_and_supporting_above_online"
            controller_info = main_facility_controllers  # Use all controllers found
            supporting_info = supporting_above_controllers  # Use all supporting above controllers found
            main_callsigns = [
                c.get("callsign", "Unknown") for c in main_facility_controllers
            ]
            support_callsigns = [
                c.get("callsign", "Unknown") for c in supporting_above_controllers
            ]
            logging.info(
                f"Main Facility AND Supporting Above Facility ONLINE: Main Facility: {', '.join(main_callsigns)}, "
                f"Supporting Above: {', '.join(support_callsigns)}"
            )
        elif main_facility_controllers:
            # Main facility is online but no supporting above facilities
            status = "main_facility_online"
            controller_info = main_facility_controllers  # Use all controllers found
            supporting_info = []
            main_callsigns = [
                c.get("callsign", "Unknown") for c in main_facility_controllers
            ]
            logging.info(f"Main Facility ONLINE: {', '.join(main_callsigns)}")
        elif supporting_above_controllers:
            # Main facility offline but supporting above facilities online
            status = "supporting_above_online"
            controller_info = []
            supporting_info = supporting_above_controllers  # Use all supporting above controllers found
            support_callsigns = [
                c.get("callsign", "Unknown") for c in supporting_above_controllers
            ]
            logging.info(
                f"Main Facility OFFLINE but supporting above facility ONLINE: "
                f"{', '.join(support_callsigns)}"
            )
        else:
            # Everything offline
            status = "all_offline"
            controller_info = []
            supporting_info = []
            logging.info("Main facility and supporting above facilities OFFLINE")

        if self.is_force_check:
            self.force_check_completed.emit(
                status, controller_info, supporting_info, supporting_below_controllers
            )
            self.is_force_check = False
        else:
            self.status_updated.emit(
                status, controller_info, supporting_info, supporting_below_controllers
            )

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
