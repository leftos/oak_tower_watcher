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
                                                    # Convert name format to "firstname lastname"
                                                    formatted_name = (
                                                        format_controller_name(
                                                            clean_name
                                                        )
                                                    )
                                                    controller_names[cid] = (
                                                        formatted_name
                                                    )
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
                    # Convert name format to "firstname lastname"
                    formatted_name = format_controller_name(clean_name)
                    controller_names[cid] = formatted_name

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
    """Convert 'lastname, firstname(operatinginitials)' to 'firstname lastname'"""
    # Check if the name matches the pattern "lastname, firstname(operatinginitials)"
    match = re.match(r"^([^,]+),\s*([^(]+)(?:\([^)]*\))?", name)
    if match:
        lastname = match.group(1).strip()
        firstname = match.group(2).strip()
        return f"{firstname} {lastname}"

    # If it doesn't match the pattern, return the original name
    return name


def get_controller_name(controller_info, controller_names):
    """Get the real name of a controller, using roster lookup if needed"""
    # First try the name from VATSIM data
    vatsim_name = controller_info.get("name", "").strip()

    # If VATSIM name exists and doesn't look like just a number, use it
    if vatsim_name and not vatsim_name.isdigit() and len(vatsim_name) > 2:
        return vatsim_name

    # Otherwise, try to look up by CID in our roster
    cid = str(controller_info.get("cid", ""))
    if cid in controller_names:
        return controller_names[cid]

    # Fallback to VATSIM name or "Unknown Controller"
    return vatsim_name if vatsim_name else "Unknown Controller"
