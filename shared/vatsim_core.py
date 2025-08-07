#!/usr/bin/env python3
"""
Core VATSIM API functionality without GUI dependencies
Contains the core logic for querying VATSIM API and processing controller data.
"""

import requests
import json
import logging
import re
from datetime import datetime


class VATSIMCore:
    """Core VATSIM API client without GUI dependencies"""

    def __init__(self, config):
        self.config = config

        # Load API endpoints from config
        api_config = config.get("api", {})
        self.vatsim_api_url = api_config.get(
            "vatsim_url", "https://data.vatsim.net/v3/vatsim-data.json"
        )

        # Load callsign regex patterns from config
        callsigns = config.get("callsigns", {})
        self.main_facility_patterns = callsigns.get(
            "main_facility", [r"^OAK_(?:[A-Z\d]+_)?TWR$"]
        )
        self.supporting_above_patterns = callsigns.get(
            "supporting_above", [r"^NCT_APP$", r"^OAK_\d+_CTR$"]
        )
        self.supporting_below_patterns = callsigns.get(
            "supporting_below", [r"^OAK_(?:[A-Z\d]+_)?GND$", r"^OAK_(?:[A-Z\d]+_)?DEL$"]
        )

        # Compile regex patterns for better performance (case-insensitive matching)
        # This allows capturing multiple controllers matching the same pattern
        # e.g., OAK_TWR, OAK_1_TWR, OAK_2_TWR all match ^OAK_(?:[A-Z\d]+_)?TWR$
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
            raise e
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing VATSIM API response: {e}")
            raise e

    def determine_status(self, main_facility_controllers, supporting_above_controllers, supporting_below_controllers):
        """Determine the overall status based on controller availability"""
        
        # Determine status based on what's online
        if main_facility_controllers and supporting_above_controllers:
            # Both main facility and supporting above facilities online - highest priority
            status = "main_facility_and_supporting_above_online"
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
            main_callsigns = [
                c.get("callsign", "Unknown") for c in main_facility_controllers
            ]
            logging.info(f"Main Facility ONLINE: {', '.join(main_callsigns)}")
        elif supporting_above_controllers:
            # Main facility offline but supporting above facilities online
            status = "supporting_above_online"
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
            logging.info("Main facility and supporting above facilities OFFLINE")

        return status

    def check_status(self):
        """Check current status and return structured data"""
        try:
            # Query the API
            main_controllers, supporting_above, supporting_below = self.query_vatsim_api()
            
            # Determine status
            status = self.determine_status(main_controllers, supporting_above, supporting_below)
            
            return {
                "status": status,
                "main_controllers": main_controllers or [],
                "supporting_above": supporting_above or [],
                "supporting_below": supporting_below or [],
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
            
        except Exception as e:
            logging.error(f"Error checking status: {e}")
            return {
                "status": "error",
                "main_controllers": [],
                "supporting_above": [],
                "supporting_below": [],
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "error": str(e)
            }