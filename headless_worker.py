#!/usr/bin/env python3
"""
Headless VATSIM API Worker module for VATSIM Tower Monitor
Handles background monitoring of VATSIM API for controller status without PyQt6 dependencies.
"""

import requests
import json
import logging
import re
import threading
import time
from typing import Callable, Optional, List, Tuple


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

    def is_controller_active(self, controller):
        """Check if a controller is active (not on inactive frequency 199.998)"""
        frequency = controller.get("frequency", "")
        # Convert frequency to string for comparison to handle both string and numeric types
        return str(frequency) != "199.998"

    def set_interval(self, interval):
        """Set check interval"""
        self.check_interval = max(30, interval)  # Minimum 30 seconds

    def query_vatsim_api(self) -> Tuple[Optional[List], Optional[List], Optional[List]]:
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
                if any(regex.match(callsign) for regex in self.main_facility_regex):
                    main_facility_controllers.append(controller)

                # Check for supporting above facility controllers using regex patterns
                elif any(
                    regex.match(callsign) for regex in self.supporting_above_regex
                ):
                    supporting_above_controllers.append(controller)

                # Check for supporting below controllers using regex patterns
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
            if self.error_occurred_callback:
                self.error_occurred_callback(f"API Error: {str(e)}")
            return None, None, None
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing VATSIM API response: {e}")
            if self.error_occurred_callback:
                self.error_occurred_callback(f"JSON Error: {str(e)}")
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
            controller_info = main_facility_controllers
            supporting_info = supporting_above_controllers
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
            controller_info = main_facility_controllers
            supporting_info = []
            main_callsigns = [
                c.get("callsign", "Unknown") for c in main_facility_controllers
            ]
            logging.info(f"Main Facility ONLINE: {', '.join(main_callsigns)}")
        elif supporting_above_controllers:
            # Main facility offline but supporting above facilities online
            status = "supporting_above_online"
            controller_info = []
            supporting_info = supporting_above_controllers
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

        # Call the status updated callback
        if self.status_updated_callback:
            self.status_updated_callback(
                status, controller_info, supporting_info, supporting_below_controllers
            )

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