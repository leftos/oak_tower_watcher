#!/usr/bin/env python3
"""
Utility functions for VATSIM Tower Monitor
Contains helper functions for color manipulation, rating translation, and instance locking.
"""

import os
import sys
import logging
import re
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup, Tag

# fcntl is only available on Unix-like systems
if sys.platform != "win32":
    import fcntl

# Global variable to store lock file handle
_lock_file = None


def darken_color_for_notification(rgb_values, factor=0.6):
    """
    Darken an RGB color for notification backgrounds to ensure white text readability.

    Args:
        rgb_values: List or tuple of [R, G, B] values (0-255)
        factor: Darkening factor (0.0 = black, 1.0 = original color)

    Returns:
        String in format "rgb(r, g, b)" with darkened values
    """
    try:
        r, g, b = rgb_values
        # Apply darkening factor and ensure minimum darkness for readability
        darkened_r = max(0, min(255, int(r * factor)))
        darkened_g = max(0, min(255, int(g * factor)))
        darkened_b = max(0, min(255, int(b * factor)))

        # Ensure the color is dark enough for white text (luminance check)
        luminance = (0.299 * darkened_r + 0.587 * darkened_g + 0.114 * darkened_b) / 255
        if luminance > 0.5:  # Too bright for white text
            # Further darken if needed
            additional_factor = 0.4
            darkened_r = int(darkened_r * additional_factor)
            darkened_g = int(darkened_g * additional_factor)
            darkened_b = int(darkened_b * additional_factor)

        return f"rgb({darkened_r}, {darkened_g}, {darkened_b})"
    except (ValueError, TypeError, IndexError):
        # Fallback to a safe dark color
        return "rgb(64, 64, 64)"


def translate_controller_rating(rating_id):
    """Translate VATSIM controller rating ID to human-readable name"""
    # VATSIM Controller Ratings mapping based on https://vatsim.dev/resources/ratings/
    rating_map = {
        -1: "Inactive",
        0: "Suspended",
        1: "Pilot/Observer",
        2: "Student Controller (S1)",
        3: "Tower Controller (S2)",
        4: "TMA Controller (S3)",
        5: "Enroute Controller (C1)",
        6: "Senior Controller (C2)",
        7: "Senior Controller (C3)",
        8: "Instructor (I1)",
        9: "Senior Instructor (I2)",
        10: "Senior Instructor (I3)",
        11: "Supervisor (SUP)",
        12: "Administrator (ADM)",
    }

    try:
        # Convert rating to integer if it's a string
        if isinstance(rating_id, str):
            rating_id = int(rating_id)
        return rating_map.get(rating_id, f"Unknown Rating ({rating_id})")
    except (ValueError, TypeError):
        return f"Invalid Rating ({rating_id})"


def acquire_instance_lock():
    """
    Acquire an exclusive lock to prevent multiple instances.
    Returns True if lock acquired successfully, False if another instance is running.
    """
    global _lock_file
    lock_file_path = os.path.join(os.path.expanduser("~"), ".vatsim_monitor.lock")

    try:
        _lock_file = open(lock_file_path, "w")

        # Try to acquire exclusive lock
        if sys.platform == "win32":
            # Windows implementation using msvcrt
            import msvcrt

            try:
                msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                # Write PID to lock file
                _lock_file.write(str(os.getpid()))
                _lock_file.flush()
                return True
            except IOError:
                _lock_file.close()
                return False
        else:
            # Unix/Linux implementation using fcntl
            try:
                fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write PID to lock file
                _lock_file.write(str(os.getpid()))
                _lock_file.flush()
                return True
            except IOError:
                _lock_file.close()
                return False

    except Exception as e:
        logging.error(f"Error acquiring instance lock: {e}")
        if _lock_file:
            _lock_file.close()
        return False


def release_instance_lock():
    """Release the instance lock."""
    global _lock_file
    if _lock_file:
        try:
            if sys.platform != "win32":
                fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
            _lock_file.close()

            # Remove lock file
            lock_file_path = os.path.join(
                os.path.expanduser("~"), ".vatsim_monitor.lock"
            )
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)
        except Exception as e:
            logging.error(f"Error releasing instance lock: {e}")
        finally:
            _lock_file = None


def load_artcc_roster(roster_url):
    """
    Load ARTCC roster to translate CIDs to real names.

    Args:
        roster_url: URL to the ARTCC roster page

    Returns:
        dict: Dictionary mapping CID to controller name
    """
    controller_names = {}

    try:
        logging.info("Loading ARTCC roster...")
        response = requests.get(roster_url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Look for controller information in the roster
        # Try to find tables or structured data containing CID and names
        tables = soup.find_all("table")
        for table in tables:
            if isinstance(table, Tag):
                rows = table.find_all("tr")
                for row in rows:
                    if isinstance(row, Tag):
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2:
                            # Look for patterns that might be CID (numeric) and name
                            for i, cell in enumerate(cells):
                                text = cell.get_text(strip=True)
                                # Check if this looks like a CID (numeric ID)
                                if (
                                    text.isdigit() and len(text) >= 6
                                ):  # CIDs are typically 6+ digits
                                    cid = text
                                    # Look for name in adjacent cells
                                    for j in range(
                                        max(0, i - 2), min(len(cells), i + 3)
                                    ):
                                        if j != i:
                                            name_text = cells[j].get_text(strip=True)
                                            # Skip if it's also numeric or empty
                                            if (
                                                name_text
                                                and not name_text.isdigit()
                                                and len(name_text) > 2
                                            ):
                                                # Clean up the name (remove extra whitespace, etc.)
                                                clean_name = re.sub(
                                                    r"\s+", " ", name_text
                                                ).strip()
                                                if clean_name and not any(
                                                    char.isdigit()
                                                    for char in clean_name[:3]
                                                ):
                                                    # Convert name format to "firstname lastname" and extract initials
                                                    formatted_data = (
                                                        format_controller_name(
                                                            clean_name
                                                        )
                                                    )
                                                    controller_names[cid] = formatted_data
                                                    break

        # Also try to find div elements or other structures with controller info
        # Look for patterns like "John Doe - 1234567" or similar
        text_content = soup.get_text()
        # Pattern to match name followed by CID or CID followed by name
        patterns = [
            r"([A-Za-z\s]{3,30})\s*[-–]\s*(\d{6,})",  # Name - CID
            r"(\d{6,})\s*[-–]\s*([A-Za-z\s]{3,30})",  # CID - Name
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text_content)
            for match in matches:
                if match[0].isdigit():  # First group is CID
                    cid, name = match[0], match[1].strip()
                else:  # First group is name
                    name, cid = match[0].strip(), match[1]

                # Clean up the name
                clean_name = re.sub(r"\s+", " ", name).strip()
                if clean_name and len(clean_name) > 2:
                    # Convert name format to "firstname lastname" and extract initials
                    formatted_data = format_controller_name(clean_name)
                    controller_names[cid] = formatted_data

        logging.info(
            f"Loaded {len(controller_names)} controller names from ARTCC roster"
        )
        if controller_names:
            logging.debug(f"Sample entries: {dict(list(controller_names.items())[:3])}")

    except Exception as e:
        logging.warning(f"Could not load ARTCC roster: {e}")
        controller_names = {}

    return controller_names


def format_controller_name(name):
    """Convert 'lastname, firstname(operatinginitials)' to 'firstname lastname' and extract initials"""
    # Check if the name matches the pattern "lastname, firstname(operatinginitials)"
    match = re.match(r"^([^,]+),\s*([^(]+)(?:\(([^)]*)\))?", name)
    if match:
        lastname = match.group(1).strip()
        firstname = match.group(2).strip()
        initials = match.group(3).strip() if match.group(3) else None
        formatted_name = f"{firstname} {lastname}"
        return {"name": formatted_name, "initials": initials}

    # If it doesn't match the pattern, return the original name without initials
    return {"name": name, "initials": None}


def get_controller_name(controller_info, controller_names):
    """Get the real name of a controller, using roster lookup if needed"""
    # First try the name from VATSIM data
    vatsim_name = controller_info.get("name", "").strip()

    # Try to look up by CID in our roster first (for initials)
    cid = str(controller_info.get("cid", ""))
    if cid in controller_names:
        roster_data = controller_names[cid]
        if isinstance(roster_data, dict):
            return roster_data["name"]
        else:
            # Handle legacy string format
            return roster_data

    # If VATSIM name exists and doesn't look like just a number, use it
    if vatsim_name and not vatsim_name.isdigit() and len(vatsim_name) > 2:
        return vatsim_name

    return ""


def get_controller_initials(controller_info, controller_names):
    """Get the operating initials of a controller from roster lookup"""
    cid = str(controller_info.get("cid", ""))
    if cid in controller_names:
        roster_data = controller_names[cid]
        if isinstance(roster_data, dict):
            return roster_data.get("initials")
    return None


def calculate_time_online(logon_time_str):
    """
    Calculate time online duration from logon time string.

    Args:
        logon_time_str: Logon time string in ISO format (e.g., "2024-01-01T12:00:00.000000Z")

    Returns:
        String: Formatted duration (e.g., "2h 30m", "45m", "1h 5m")
    """
    if not logon_time_str or logon_time_str == "Unknown":
        return "Unknown"

    try:
        # Parse the logon time - handle both with and without microseconds
        if "." in logon_time_str:
            # Has microseconds
            logon_time = datetime.fromisoformat(logon_time_str.replace("Z", "+00:00"))
        else:
            # No microseconds, add Z if not present
            if not logon_time_str.endswith("Z"):
                logon_time_str += "Z"
            logon_time = datetime.fromisoformat(logon_time_str.replace("Z", "+00:00"))

        # Get current time in UTC
        current_time = datetime.now(timezone.utc)

        # Calculate duration
        duration = current_time - logon_time
        total_seconds = int(duration.total_seconds())

        # Convert to hours and minutes
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        # Format the duration
        if hours > 0:
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return "< 1m"

    except (ValueError, TypeError) as e:
        logging.warning(f"Could not parse logon time '{logon_time_str}': {e}")
        return "Unknown"


def format_controller_details(controllers: List[Dict[str, Any]], controller_names: Optional[Dict[str, Any]] = None) -> str:
    """
    Format a list of controllers with callsigns and names where available.
    
    Args:
        controllers: List of controller dictionaries
        controller_names: Optional dictionary mapping CIDs to controller names
        
    Returns:
        Formatted string with controller details
    """
    if not controllers:
        return "None"
        
    controller_names = controller_names or {}
    details = []
    
    for controller in controllers:
        callsign = controller.get('callsign', 'Unknown')
        cid = controller.get('cid', '')
        
        # Try to get controller name
        controller_name = None
        if controller_names:
            controller_name = get_controller_name(controller, controller_names)
            if controller_name and controller_name != "":
                # Format as "CALLSIGN (Name)"
                details.append(f"{callsign} ({controller_name})")
            else:
                # No name from roster, try CID
                if cid:
                    details.append(f"{callsign} ({cid})")
                else:
                    details.append(callsign)
        else:
            # Check if there's a name in the controller data itself
            vatsim_name = controller.get('name', '').strip()
            if vatsim_name and not vatsim_name.isdigit() and len(vatsim_name) > 2:
                details.append(f"{callsign} ({vatsim_name})")
            else:
                # No name available, show CID if we have it
                if cid:
                    details.append(f"{callsign} ({cid})")
                else:
                    details.append(callsign)
    
    return ", ".join(details)


def format_push_notification(
    current_status: str,
    main_controllers: Optional[List[Dict[str, Any]]] = None,
    supporting_above: Optional[List[Dict[str, Any]]] = None,
    supporting_below: Optional[List[Dict[str, Any]]] = None,
    include_priority_sound: bool = False,
    is_test: bool = False,
    controller_names: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format push notification title, message, priority and sound based on status.
    
    Args:
        current_status: The current facility status
        main_controllers: List of main facility controllers
        supporting_above: List of supporting above controllers
        supporting_below: List of supporting below controllers
        include_priority_sound: Whether to include priority and sound in response
        is_test: Whether this is a test notification
        controller_names: Optional dictionary mapping CIDs to controller names
    
    Returns:
        Dictionary containing title, message, and optionally priority/sound
    """
    main_controllers = main_controllers or []
    supporting_above = supporting_above or []
    supporting_below = supporting_below or []
    
    result = {}
    
    # Format controller details
    main_details = format_controller_details(main_controllers, controller_names)
    supporting_above_details = format_controller_details(supporting_above, controller_names)
    supporting_below_details = format_controller_details(supporting_below, controller_names)
    
    # Format based on current status
    if current_status == 'main_facility_and_supporting_above_online':
        result['title'] = "🟣 Full Coverage Active!"
        message_parts = [
            "Main facility and supporting controllers are now online.",
            f"Main: {main_details}",
            f"Supporting Above: {supporting_above_details}"
        ]
        if supporting_below:
            message_parts.append(f"Supporting Below: {supporting_below_details}")
        result['message'] = "\n".join(message_parts)
        if include_priority_sound:
            result['priority'] = 1
            result['sound'] = "magic"
            
    elif current_status == 'main_facility_online':
        result['title'] = "🟢 Main Facility Online!"
        message_parts = [
            "Main facility controllers are now active.",
            f"Controllers: {main_details}"
        ]
        if supporting_below:
            message_parts.append(f"Supporting Below: {supporting_below_details}")
        result['message'] = "\n".join(message_parts)
        if include_priority_sound:
            result['priority'] = 0
            result['sound'] = "pushover"
            
    elif current_status == 'supporting_above_online':
        result['title'] = "🟡 Supporting Facility Online"
        message_parts = [
            "Supporting controllers are active (main facility offline).",
            f"Supporting Above: {supporting_above_details}"
        ]
        if supporting_below:
            message_parts.append(f"Supporting Below: {supporting_below_details}")
        result['message'] = "\n".join(message_parts)
        if include_priority_sound:
            result['priority'] = 0
            result['sound'] = "intermission"
            
    elif current_status == 'all_offline':
        result['title'] = "🔴 All Facilities Offline"
        result['message'] = "All monitored controllers have gone offline."
        if include_priority_sound:
            result['priority'] = 0
            result['sound'] = "falling"
            
    else:
        # Fallback for unknown statuses (mainly for test notifications)
        result['title'] = "🔍 Status Test Notification"
        message_parts = [f"Current status: {current_status or 'Unknown'}"]
        if main_controllers:
            message_parts.append(f"Main: {main_details}")
        if supporting_above:
            message_parts.append(f"Supporting Above: {supporting_above_details}")
        if supporting_below:
            message_parts.append(f"Supporting Below: {supporting_below_details}")
        result['message'] = "\n".join(message_parts)
        if include_priority_sound:
            result['priority'] = -1
            result['sound'] = "none"
    
    return result


def get_facility_display_name(
    current_status: str,
    main_controllers: Optional[List[Dict[str, Any]]] = None,
    supporting_above: Optional[List[Dict[str, Any]]] = None,
    fallback_name: str = "Main Facility"
) -> str:
    """
    Get dynamic facility display name based on current status and active controllers.
    
    Args:
        current_status: The current facility status
        main_controllers: List of main facility controllers
        supporting_above: List of supporting above controllers
        fallback_name: Fallback name when no specific facility can be determined
    
    Returns:
        String: Appropriate facility display name
    """
    main_controllers = main_controllers or []
    supporting_above = supporting_above or []
    
    # If exactly one main facility is online, use its callsign
    if len(main_controllers) == 1 and current_status in ["main_facility_online", "main_facility_and_supporting_above_online"]:
        callsign = main_controllers[0].get('callsign', '')
        if callsign:
            # Extract base callsign (remove _1, _2, etc. suffixes for display)
            base_callsign = re.sub(r'_\d+_', '_', callsign)  # OAK_1_TWR -> OAK_TWR
            return base_callsign
    
    # If main facility is offline but exactly one supporting facility is online
    if len(supporting_above) == 1 and current_status == "supporting_above_online" and not main_controllers:
        callsign = supporting_above[0].get('callsign', '')
        if callsign:
            base_callsign = re.sub(r'_\d+_', '_', callsign)
            return base_callsign
    
    # For all other cases (multiple facilities, all offline, or mixed), use generic term
    return fallback_name


def extract_facility_name_from_callsign(callsign: str) -> str:
    """
    Extract a readable facility name from a callsign.
    
    Args:
        callsign: Controller callsign (e.g., "OAK_TWR", "NCT_APP")
    
    Returns:
        String: Readable facility name (e.g., "Oakland Tower", "NorCal Approach")
    """
    if not callsign:
        return "Unknown Facility"
    
    # Remove numeric suffixes for cleaner display
    clean_callsign = re.sub(r'_\d+(?=_|$)', '', callsign)
    
    # Common facility type mappings
    facility_types = {
        'TWR': 'Tower',
        'APP': 'Approach',
        'DEP': 'Departure',
        'CTR': 'Center',
        'GND': 'Ground',
        'DEL': 'Delivery',
        'FSS': 'Flight Service'
    }
    
    # Extract airport/facility code and type
    parts = clean_callsign.split('_')
    if len(parts) >= 2:
        facility_code = parts[0]
        facility_type = parts[-1]
        
        # Map facility type to readable name
        type_name = facility_types.get(facility_type, facility_type.title())
        
        # Special handling for some well-known facility codes
        facility_names = {
            'NCT': 'NorCal',
            'SCT': 'SoCal',
            'OAK': 'Oakland',
            'SFO': 'San Francisco',
            'LAX': 'Los Angeles',
            'ZOA': 'Oakland Center',
            'ZLA': 'Los Angeles Center'
        }
        
        facility_name = facility_names.get(facility_code, facility_code)
        return f"{facility_name} {type_name}"
    
    return callsign
